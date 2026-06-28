"""Kanban board state management for TANGLE"""
import json
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional

KANBAN_PATH = Path(__file__).resolve().parent.parent / ".tangle-kanban.json"

COLUMNS = ["backlog", "ready", "in_progress", "blocked", "review", "testing", "done"]


@dataclass
class KanbanCard:
    id: str
    task_id: str
    title: str
    agent_id: str = ""
    status: str = "backlog"
    column: str = "backlog"
    created_at: str = ""
    updated_at: str = ""
    moved_at: str = ""
    branch: str = ""
    file_changes: list[str] = field(default_factory=list)
    run_id: str = ""
    artifact: str = ""
    blocked_by: str = ""
    wip_limit: int = 3
    sla_minutes: int = 60
    notes: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at


class KanbanBoard:
    def __init__(self, path: str = None):
        self.path = Path(path or str(KANBAN_PATH))
        self.cards: dict[str, KanbanCard] = {}
        self.column_order: list[str] = COLUMNS[:]
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text())
                self.cards = {k: KanbanCard(**v) for k, v in data.get("cards", {}).items()}
                self.column_order = data.get("column_order", COLUMNS[:])
            except Exception:
                self.cards = {}

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "cards": {k: asdict(v) for k, v in self.cards.items()},
            "column_order": self.column_order,
            "updated_at": datetime.utcnow().isoformat(),
        }
        self.path.write_text(json.dumps(data, indent=2))

    def get_all(self) -> list[dict]:
        return [asdict(c) for c in self.cards.values()]

    def get_by_column(self, column: str) -> list[dict]:
        return [asdict(c) for c in self.cards.values() if c.column == column]

    def get_by_agent(self, agent_id: str) -> list[dict]:
        return [asdict(c) for c in self.cards.values() if c.agent_id == agent_id]

    def get_by_task(self, task_id: str) -> Optional[dict]:
        for c in self.cards.values():
            if c.task_id == task_id:
                return asdict(c)
        return None

    def create(self, task_id: str, title: str, agent_id: str = "", column: str = "backlog") -> dict:
        card_id = f"K-{len(self.cards) + 1:03d}"
        card = KanbanCard(id=card_id, task_id=task_id, title=title, agent_id=agent_id, column=column)
        self.cards[card_id] = card
        self._save()
        return asdict(card)

    def move(self, card_id: str, column: str) -> Optional[dict]:
        card = self.cards.get(card_id)
        if not card:
            return None
        card.column = column
        card.moved_at = datetime.utcnow().isoformat()
        card.updated_at = card.moved_at
        if column == "done":
            card.status = "done"
        elif column == "in_progress":
            card.status = "in_progress"
        elif column == "blocked":
            card.status = "blocked"
        self._save()
        return asdict(card)

    def update(self, card_id: str, **kwargs) -> Optional[dict]:
        card = self.cards.get(card_id)
        if not card:
            return None
        for key, value in kwargs.items():
            if hasattr(card, key):
                setattr(card, key, value)
        card.updated_at = datetime.utcnow().isoformat()
        self._save()
        return asdict(card)

    def delete(self, card_id: str) -> bool:
        if card_id in self.cards:
            del self.cards[card_id]
            self._save()
            return True
        return False

    def get_stats(self) -> dict:
        total = len(self.cards)
        by_column = {}
        for col in COLUMNS:
            by_column[col] = len([c for c in self.cards.values() if c.column == col])
        by_agent = {}
        for c in self.cards.values():
            agent = c.agent_id or "unassigned"
            by_agent[agent] = by_agent.get(agent, 0) + 1
        blocked = [asdict(c) for c in self.cards.values() if c.column == "blocked"]
        wip_violations = []
        for col in COLUMNS:
            cards_in_col = [c for c in self.cards.values() if c.column == col]
            if len(cards_in_col) > 3:  # Default WIP limit
                wip_violations.append({"column": col, "count": len(cards_in_col)})
        return {
            "total": total,
            "by_column": by_column,
            "by_agent": by_agent,
            "blocked": blocked,
            "wip_violations": wip_violations,
        }

    def sync_from_tasks(self, tasks: list[dict]):
        """Sync kanban cards from task manager tasks."""
        task_map = {t["id"]: t for t in tasks}
        # Create cards for tasks that don't have them
        for task in tasks:
            existing = self.get_by_task(task["id"])
            if not existing:
                col = "backlog"
                if task["status"] == "in_progress":
                    col = "in_progress"
                elif task["status"] == "blocked":
                    col = "blocked"
                elif task["status"] == "review":
                    col = "review"
                elif task["status"] == "done":
                    col = "done"
                self.create(task["id"], task["title"], task.get("assigned_to", ""), col)
        # Update existing cards
        for card in self.cards.values():
            task = task_map.get(card.task_id)
            if task:
                if task["status"] == "in_progress" and card.column == "backlog":
                    card.column = "in_progress"
                elif task["status"] == "done" and card.column != "done":
                    card.column = "done"
                card.agent_id = task.get("assigned_to", card.agent_id)
                card.updated_at = datetime.utcnow().isoformat()
        self._save()
