"""TASKLIST.md management — source of truth for TANGLE agent tasks"""
import re, json, os
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional

TASKLIST_PATH = Path(__file__).resolve().parent.parent / "TASKLIST.md"

STATUSES = ["todo", "in_progress", "blocked", "review", "done"]
PRIORITIES = ["critical", "high", "medium", "low"]


@dataclass
class Task:
    id: str
    title: str
    description: str
    status: str = "todo"
    priority: str = "medium"
    assigned_to: str = ""
    created_at: str = ""
    updated_at: str = ""
    completed_at: Optional[str] = None
    dependencies: list[str] = field(default_factory=list)
    linked_node: str = ""
    linked_commit: str = ""
    linked_run: str = ""
    notes: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at


class TaskListManager:
    def __init__(self, path: str = None):
        self.path = Path(path or str(TASKLIST_PATH))
        self.tasks: dict[str, Task] = {}
        self._load()

    def _load(self):
        if not self.path.exists():
            self._create_default()
            return

        content = self.path.read_text()
        # Parse markdown table format: | ID | Title | Status | Priority | Assigned |
        lines = content.split("\n")
        in_table = False
        for line in lines:
            line = line.strip()
            if line.startswith("|---") or line.startswith("| ID"):
                in_table = True
                continue
            if in_table and line.startswith("|"):
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 5:
                    task_id, title, status, priority, assigned = parts[0], parts[1], parts[2], parts[3], parts[4]
                    # Parse extra fields from description if present
                    desc = ""
                    if len(parts) > 5:
                        desc = parts[5]
                    self.tasks[task_id] = Task(
                        id=task_id, title=title, description=desc,
                        status=status if status in STATUSES else "todo",
                        priority=priority if priority in PRIORITIES else "medium",
                        assigned_to=assigned,
                    )

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "# TASKLIST.md — Source of Truth for TANGLE Agents",
            "",
            "*All agents read this file first and last. Status must be one of: " + ", ".join(STATUSES) + "*",
            "",
            "| ID | Title | Status | Priority | Assigned | Description |",
            "|---|---|---|---|---|---|",
        ]
        for t in sorted(self.tasks.values(), key=lambda x: (PRIORITIES.index(x.priority) if x.priority in PRIORITIES else 2, x.created_at)):
            lines.append(f"| {t.id} | {t.title} | {t.status} | {t.priority} | {t.assigned_to} | {t.description} |")
        lines.append("")
        self.path.write_text("\n".join(lines))

    def _create_default(self):
        self.tasks = {
            "T-001": Task(id="T-001", title="Setup project structure", status="done", priority="critical", assigned_to="07", description="Initialize backend and frontend"),
            "T-002": Task(id="T-002", title="Implement agent orchestration", status="done", priority="critical", assigned_to="13", description="Free gateway + tool calling"),
            "T-003": Task(id="T-003", title="Add LangGraph integration", status="done", priority="high", assigned_to="03", description="StateGraph engine for agent loops"),
            "T-004": Task(id="T-004", title="Build review harness", status="done", priority="high", assigned_to="04", description="Three-persona validation + auto-fix"),
            "T-005": Task(id="T-005", title="Implement TASKLIST.md UI", status="in_progress", priority="high", assigned_to="03", description="Frontend panel for task governance"),
            "T-006": Task(id="T-006", title="Build kanban board", status="todo", priority="high", assigned_to="03", description="Live kanban linked to agent work"),
            "T-007": Task(id="T-007", title="Add run history", status="todo", priority="medium", assigned_to="15", description="Store and replay previous runs"),
            "T-008": Task(id="T-008", title="Connect flows to real execution", status="todo", priority="high", assigned_to="03", description="Replace simulated flows with backend calls"),
        }
        self._save()

    def get_all(self) -> list[dict]:
        return [asdict(t) for t in self.tasks.values()]

    def get_by_status(self, status: str) -> list[dict]:
        return [asdict(t) for t in self.tasks.values() if t.status == status]

    def get_by_agent(self, agent_id: str) -> list[dict]:
        return [asdict(t) for t in self.tasks.values() if t.assigned_to == agent_id]

    def get_active(self) -> list[dict]:
        return [asdict(t) for t in self.tasks.values() if t.status in ("in_progress", "blocked")]

    def create(self, title: str, description: str = "", priority: str = "medium", assigned_to: str = "", dependencies: list[str] = None) -> dict:
        # Generate next ID
        max_num = 0
        for tid in self.tasks:
            match = re.match(r"T-(\d+)", tid)
            if match:
                max_num = max(max_num, int(match.group(1)))
        task_id = f"T-{max_num + 1:03d}"
        task = Task(id=task_id, title=title, description=description, priority=priority, assigned_to=assigned_to, dependencies=dependencies or [])
        self.tasks[task_id] = task
        self._save()
        return asdict(task)

    def update(self, task_id: str, **kwargs) -> Optional[dict]:
        task = self.tasks.get(task_id)
        if not task:
            return None
        for key, value in kwargs.items():
            if hasattr(task, key):
                setattr(task, key, value)
        task.updated_at = datetime.utcnow().isoformat()
        if kwargs.get("status") == "done" and not task.completed_at:
            task.completed_at = datetime.utcnow().isoformat()
        self._save()
        return asdict(task)

    def delete(self, task_id: str) -> bool:
        if task_id in self.tasks:
            del self.tasks[task_id]
            self._save()
            return True
        return False

    def get_stats(self) -> dict:
        total = len(self.tasks)
        by_status = {}
        for s in STATUSES:
            by_status[s] = len([t for t in self.tasks.values() if t.status == s])
        by_priority = {}
        for p in PRIORITIES:
            by_priority[p] = len([t for t in self.tasks.values() if t.priority == p])
        by_agent = {}
        for t in self.tasks.values():
            agent = t.assigned_to or "unassigned"
            by_agent[agent] = by_agent.get(agent, 0) + 1
        return {"total": total, "by_status": by_status, "by_priority": by_priority, "by_agent": by_agent}

    def get_content(self) -> str:
        if self.path.exists():
            return self.path.read_text()
        return ""

    def update_content(self, content: str):
        self.path.write_text(content)
        self._load()
