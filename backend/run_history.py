"""Run history storage and replay for TANGLE agent executions"""
import json, uuid
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional

HISTORY_DIR = Path(__file__).resolve().parent.parent / ".tangle-history"
RUNS_PATH = HISTORY_DIR / "runs.json"


@dataclass
class RunEvent:
    type: str  # agent_start, agent_think, tool_call, tool_result, agent_complete, agent_error
    agent_id: str
    data: dict
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()


@dataclass
class AgentRun:
    id: str
    flow_id: str
    status: str = "running"  # running, completed, failed, stopped
    started_at: str = ""
    completed_at: Optional[str] = None
    events: list[RunEvent] = field(default_factory=list)
    agents_used: list[str] = field(default_factory=list)
    total_tokens: int = 0
    total_cost: float = 0.0
    error: Optional[str] = None
    artifacts: list[str] = field(default_factory=list)
    commits: list[str] = field(default_factory=list)
    notes: str = ""

    def __post_init__(self):
        if not self.started_at:
            self.started_at = datetime.utcnow().isoformat()


class RunHistory:
    def __init__(self, path: str = None):
        self.path = Path(path or str(RUNS_PATH))
        self.runs: dict[str, AgentRun] = {}
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text())
                for run_id, run_data in data.items():
                    events = [RunEvent(**e) for e in run_data.get("events", [])]
                    self.runs[run_id] = AgentRun(**{**run_data, "events": events})
            except Exception:
                self.runs = {}

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        for run_id, run in self.runs.items():
            run_dict = asdict(run)
            run_dict["events"] = [asdict(e) for e in run.events]
            data[run_id] = run_dict
        self.path.write_text(json.dumps(data, indent=2))

    def create(self, flow_id: str) -> str:
        run_id = str(uuid.uuid4())[:8]
        run = AgentRun(id=run_id, flow_id=flow_id)
        self.runs[run_id] = run
        self._save()
        return run_id

    def add_event(self, run_id: str, event: RunEvent):
        run = self.runs.get(run_id)
        if run:
            run.events.append(event)
            if event.agent_id not in run.agents_used:
                run.agents_used.append(event.agent_id)
            self._save()

    def complete(self, run_id: str, status: str = "completed", error: str = None, artifacts: list[str] = None, commits: list[str] = None):
        run = self.runs.get(run_id)
        if run:
            run.status = status
            run.completed_at = datetime.utcnow().isoformat()
            if error:
                run.error = error
            if artifacts:
                run.artifacts.extend(artifacts)
            if commits:
                run.commits.extend(commits)
            self._save()

    def get(self, run_id: str) -> Optional[dict]:
        run = self.runs.get(run_id)
        if run:
            result = asdict(run)
            result["events"] = [asdict(e) for e in run.events]
            return result
        return None

    def get_all(self, limit: int = 50) -> list[dict]:
        runs = sorted(self.runs.values(), key=lambda r: r.started_at, reverse=True)[:limit]
        return [asdict(r) for r in runs]

    def get_by_flow(self, flow_id: str) -> list[dict]:
        runs = [r for r in self.runs.values() if r.flow_id == flow_id]
        return [asdict(r) for r in sorted(runs, key=lambda r: r.started_at, reverse=True)]

    def delete(self, run_id: str) -> bool:
        if run_id in self.runs:
            del self.runs[run_id]
            self._save()
            return True
        return False

    def get_stats(self) -> dict:
        total = len(self.runs)
        by_status = {}
        for status in ("running", "completed", "failed", "stopped"):
            by_status[status] = len([r for r in self.runs.values() if r.status == status])
        by_flow = {}
        for r in self.runs.values():
            by_flow[r.flow_id] = by_flow.get(r.flow_id, 0) + 1
        return {"total": total, "by_status": by_status, "by_flow": by_flow}
