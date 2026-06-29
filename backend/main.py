from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional
import psutil
import platform
import subprocess
import signal
import os, json, shutil
import asyncio
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
import httpx
from collections import defaultdict
import time as _time

# Simple in-memory rate limiter (single-user local, no Redis needed)
_rate_limits: dict[str, list[float]] = defaultdict(list)

def _check_rate_limit(key: str, max_requests: int = 30, window: float = 60.0) -> bool:
    """Return True if request is allowed, False if rate-limited."""
    now = _time.time()
    _rate_limits[key] = [t for t in _rate_limits[key] if now - t < window]
    if len(_rate_limits[key]) >= max_requests:
        return False
    _rate_limits[key].append(now)
    return True

# Structured JSON logging support
from pythonjsonlogger import jsonlogger

# Configure logging - JSON format if TANGLE_LOG_JSON=true, else human-readable
log_json = os.getenv("TANGLE_LOG_JSON", "false").lower() in ("true", "1", "yes")
if log_json:
    log_handler = logging.StreamHandler()
    formatter = jsonlogger.JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    log_handler.setFormatter(formatter)
    logging.basicConfig(level=logging.INFO, handlers=[log_handler])
else:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
logger = logging.getLogger("tangle.api")

# Load .env from repo root (parent of backend/) regardless of CWD
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

class AgentTask(BaseModel):
    agent_id: str
    task: str

class WorkflowTask(BaseModel):
    agent_id: str
    task: str

class WorkflowRequest(BaseModel):
    tasks: list[WorkflowTask]

class LangGraphRequest(BaseModel):
    agent_id: str
    task: str
    max_turns: int = 10

from free_gateway import FreeGateway
from agent_orchestrator import AgentOrchestrator, AGENT_DEFS
from langgraph_engine import LangGraphEngine
from task_manager import TaskListManager
from kanban_store import KanbanBoard
from run_history import RunHistory
from wiki_vault import WikiVault
import metrics as tangle_metrics

gateway = FreeGateway()
orchestrator = AgentOrchestrator(gateway)
langgraph_engine = LangGraphEngine(gateway, orchestrator=orchestrator)
langgraph_engine.compile()
task_manager = TaskListManager()
kanban_board = KanbanBoard()
run_history = RunHistory()
wiki_vault = WikiVault()

app = FastAPI(title="TANGLE Agentic API")

@app.on_event("startup")
async def startup_event():
    """Initialize metrics on startup."""
    tangle_metrics.init_metrics()
    logger.info("TANGLE API started")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────
# Health
# ─────────────────────────────────────────────────────────────
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "TANGLE API",
        "version": "2.0.0",
        "agents": 16,
        "timestamp": datetime.utcnow().isoformat()
    }

# ─────────────────────────────────────────────────────────────
# Prometheus Metrics
# ─────────────────────────────────────────────────────────────
@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(
        content=tangle_metrics.get_metrics(),
        media_type=tangle_metrics.get_metrics_content_type()
    )

# ─────────────────────────────────────────────────────────────
# Agents
# ─────────────────────────────────────────────────────────────
@app.get("/agents")
async def get_agents():
    return [
        {"id": "01", "name": "Scout", "codename": "SCOUT", "role": "Researcher", "collection": "research_memories"},
        {"id": "02", "name": "Blueprint", "codename": "BLUEPRINT", "role": "Architect", "collection": "architecture_memories"},
        {"id": "03", "name": "Forge", "codename": "FORGE", "role": "Code Writer", "collection": "code_memories"},
        {"id": "04", "name": "Hammer", "codename": "HAMMER", "role": "QA Engineer", "collection": "qa_memories"},
        {"id": "05", "name": "Aegis", "codename": "AEGIS", "role": "Security Sentinel", "collection": "security_memories"},
        {"id": "06", "name": "Pipeline", "codename": "PIPELINE", "role": "Data Engineer", "collection": "data_memories"},
        {"id": "07", "name": "Launcher", "codename": "LAUNCHER", "role": "DevOps Runner", "collection": "devops_memories"},
        {"id": "08", "name": "Canvas", "codename": "CANVAS", "role": "UX Designer", "collection": "ux_memories"},
        {"id": "09", "name": "Scribe", "codename": "SCRIBE", "role": "Technical Writer", "collection": "docs_memories"},
        {"id": "10", "name": "Tracer", "codename": "TRACER", "role": "Debugger", "collection": "debug_memories"},
        {"id": "11", "name": "Turbo", "codename": "TURBO", "role": "Performance Tuner", "collection": "performance_memories"},
        {"id": "12", "name": "Bridge", "codename": "BRIDGE", "role": "Integration Specialist", "collection": "integration_memories"},
        {"id": "13", "name": "Maestro", "codename": "MAESTRO", "role": "Orchestrator", "collection": "orchestrator_memories"},
        {"id": "14", "name": "Packager", "codename": "PACKAGER", "role": "Package Manager", "collection": "package_memories"},
        {"id": "15", "name": "Inspector", "codename": "INSPECTOR", "role": "Examination Agent", "collection": "examination_memories"},
        {"id": "16", "name": "Watchdog", "codename": "WATCHDOG", "role": "System Guardian", "collection": "system_memories"},
    ]

# ─────────────────────────────────────────────────────────────
# System Monitor (Agent-16: WATCHDOG)
# ─────────────────────────────────────────────────────────────
def bytes_to_mb(b: int) -> float:
    return round(b / (1024 * 1024), 1)

@app.get("/api/system/metrics")
async def get_system_metrics():
    """
    WATCHDOG: Real-time macOS system resource snapshot.
    Returns top 20 processes by CPU, plus overall system stats.
    """
    cpu_percent = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')

    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info', 'username', 'status', 'create_time']):
        try:
            info = proc.info
            if info['memory_info'] is None:
                continue
            processes.append({
                "pid": info['pid'],
                "name": info['name'] or "unknown",
                "cpu": round(info['cpu_percent'] or 0, 1),
                "memory_mb": bytes_to_mb(info['memory_info'].rss),
                "vsz_mb": bytes_to_mb(info['memory_info'].vms),
                "user": info['username'] or "system",
                "status": info['status'] or "unknown",
                "started": datetime.fromtimestamp(info['create_time']).strftime('%H:%M:%S') if info.get('create_time') else "?",
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # Sort by CPU then memory
    top_by_cpu = sorted(processes, key=lambda x: x['cpu'], reverse=True)[:20]

    # Build alerts
    alerts = []
    for p in top_by_cpu:
        if p['cpu'] > 85:
            alerts.append({"pid": p['pid'], "name": p['name'], "reason": f"CPU {p['cpu']}% — critical threshold", "severity": "critical"})
        elif p['cpu'] > 60:
            alerts.append({"pid": p['pid'], "name": p['name'], "reason": f"CPU {p['cpu']}% — warning threshold", "severity": "warn"})
        if p['memory_mb'] > 800:
            alerts.append({"pid": p['pid'], "name": p['name'], "reason": f"RAM {p['memory_mb']}MB — critical threshold", "severity": "critical"})
        elif p['memory_mb'] > 300:
            alerts.append({"pid": p['pid'], "name": p['name'], "reason": f"RAM {p['memory_mb']}MB — warning threshold", "severity": "warn"})

    return {
        "cpu_percent": cpu_percent,
        "total_ram_mb": bytes_to_mb(mem.total),
        "free_ram_mb": bytes_to_mb(mem.available),
        "used_ram_pct": mem.percent,
        "disk_total_gb": round(disk.total / (1024**3), 1),
        "disk_free_gb": round(disk.free / (1024**3), 1),
        "disk_used_pct": disk.percent,
        "platform": platform.platform(),
        "processes": top_by_cpu,
        "alerts": alerts[:10],
        "timestamp": datetime.utcnow().isoformat(),
    }

class KillRequest(BaseModel):
    pid: int
    signal_type: str = "SIGTERM"  # SIGTERM or SIGKILL
    reason: str = "User requested"

@app.post("/api/system/kill")
async def kill_process(req: KillRequest):
    """
    WATCHDOG: Kill a process by PID.
    SIGTERM first (graceful), then SIGKILL if needed.
    Requires orchestrator approval token in production.
    """
    pid = req.pid

    # Safety: never kill system processes
    if pid <= 100:
        raise HTTPException(status_code=403, detail="Cannot kill system processes (PID ≤ 100)")
    if pid == os.getpid():
        raise HTTPException(status_code=403, detail="Cannot kill self")

    try:
        proc = psutil.Process(pid)
        name = proc.name()

        if req.signal_type == "SIGKILL":
            proc.kill()
        else:
            proc.terminate()
            # Wait up to 5s then force kill
            try:
                proc.wait(timeout=5)
            except psutil.TimeoutExpired:
                proc.kill()

        return {
            "success": True,
            "pid": pid,
            "name": name,
            "signal": req.signal_type,
            "reason": req.reason,
            "timestamp": datetime.utcnow().isoformat(),
            "message": f"Process '{name}' (PID {pid}) terminated successfully"
        }
    except psutil.NoSuchProcess:
        raise HTTPException(status_code=404, detail=f"Process {pid} not found")
    except psutil.AccessDenied:
        raise HTTPException(status_code=403, detail=f"Access denied for process {pid}")

@app.get("/api/system/processes")
async def get_top_processes():
    """Top 20 processes sorted by RAM usage."""
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info', 'username', 'status']):
        try:
            info = proc.info
            if info['memory_info'] is None:
                continue
            processes.append({
                "pid": info['pid'],
                "name": info['name'],
                "cpu": round(info['cpu_percent'] or 0, 1),
                "memory_mb": bytes_to_mb(info['memory_info'].rss),
                "user": info['username'] or "system",
                "status": info['status'],
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return sorted(processes, key=lambda x: x['memory_mb'], reverse=True)[:20]

# ─────────────────────────────────────────────────────────────
# Terminal Command Execution
# ─────────────────────────────────────────────────────────────
class TerminalCommand(BaseModel):
    command: str
    timeout: int = 30

@app.post("/api/terminal/execute")
async def execute_terminal(cmd: TerminalCommand):
    project_root = Path(__file__).parent.parent
    try:
        process = await asyncio.create_subprocess_shell(
            cmd.command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(project_root),
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=cmd.timeout
            )
        except asyncio.TimeoutError:
            process.kill()
            return {
                "output": f"[TIMEOUT] Command exceeded {cmd.timeout}s limit",
                "stderr": "",
                "exit_code": -1,
            }

        return {
            "output": stdout.decode(errors="replace"),
            "stderr": stderr.decode(errors="replace"),
            "exit_code": process.returncode,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ─────────────────────────────────────────────────────────────
# Agent Execution
# ─────────────────────────────────────────────────────────────
class AgentResponse(BaseModel):
    agent_id: str
    result: str
    turns: int
    error: str = ""

ws_connections: dict[str, list[WebSocket]] = {}

async def broadcast(agent_id: str, event: dict):
    for ws in ws_connections.get(agent_id, []):
        try:
            await ws.send_json(event)
        except Exception:
            pass
    for ws in ws_connections.get("_all", []):
        try:
            await ws.send_json(event)
        except Exception:
            pass

@orchestrator.on_event
async def handle_orchestrator_event(event: dict):
    agent_id = event.get("agent_id", "system")
    await broadcast(agent_id, event)

@app.websocket("/api/ws/agents")
async def agent_websocket(ws: WebSocket):
    await ws.accept()
    agent_id = "_all"
    try:
        data = await ws.receive_text()
        try:
            payload = json.loads(data)
            if "agent_id" in payload:
                agent_id = payload["agent_id"]
        except json.JSONDecodeError:
            pass
    except Exception:
        pass

    if agent_id not in ws_connections:
        ws_connections[agent_id] = []
    ws_connections[agent_id].append(ws)

    try:
        while True:
            data = await ws.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("action") == "execute":
                    asyncio.create_task(orchestrator.execute(msg["agent_id"], msg["task"]))
                elif msg.get("action") == "stop":
                    orchestrator.stop()
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        pass
    finally:
        if agent_id in ws_connections:
            ws_connections[agent_id] = [w for w in ws_connections[agent_id] if w != ws]

@app.post("/api/agents/execute")
async def execute_agent(req: AgentTask):
    logger.info(f"Agent execute: agent_id={req.agent_id}, task={req.task[:50]}...")
    run_id = run_history.create(f"agent_{req.agent_id}")
    await run_history.add_event(run_id, {"type": "agent_start", "agent_id": req.agent_id, "data": {"task": req.task}})
    result = await orchestrator.execute(req.agent_id, req.task)
    if "error" in result:
        await run_history.complete(run_id, "failed", result.get("error"))
    else:
        await run_history.complete(run_id, "completed")
    return result

@app.post("/api/agents/workflow")
async def execute_workflow(req: WorkflowRequest):
    logger.info(f"Workflow execute: {len(req.tasks)} tasks")
    tasks = [{"agent_id": t.agent_id, "task": t.task} for t in req.tasks]
    result = await orchestrator.workflow(tasks)
    return result

@app.post("/api/agents/lg/execute")
async def execute_agent_lg(req: LangGraphRequest):
    logger.info(f"LangGraph execute: agent_id={req.agent_id}, task={req.task[:50]}..., max_turns={req.max_turns}")
    result = await langgraph_engine.run(req.agent_id, req.task, max_turns=req.max_turns)
    return result

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...), entity: str = Form(...)):
    if not _check_rate_limit("upload", max_requests=10, window=60.0):
        raise HTTPException(status_code=429, detail="Rate limit: max 10 uploads per minute")
    if not entity or not entity.strip() or len(entity) > 500:
        raise HTTPException(status_code=400, detail="Entity name required (max 500 chars)")
    try:
        logger.info(f"Uploading file {file.filename} for entity {entity}")
        uploads_dir = Path(__file__).parent.parent / "uploads"
        uploads_dir.mkdir(exist_ok=True)

        # Sanitize filename: strip path components to prevent path traversal
        safe_name = Path(file.filename).name  # removes any directory parts
        if not safe_name or safe_name.startswith("."):
            raise HTTPException(status_code=400, detail="Invalid filename")
        # Block extremely long names
        if len(safe_name) > 255:
            safe_name = safe_name[:255]

        file_path = uploads_dir / safe_name
        # Final check: resolved path must be inside uploads_dir
        if not file_path.resolve().is_relative_to(uploads_dir.resolve()):
            raise HTTPException(status_code=400, detail="Invalid file path")

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        parsed_data = await orchestrator.ingest(str(file_path), entity)
        return {
            "success": True,
            "filename": safe_name,
            "filepath": str(file_path),
            "parsed": parsed_data
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class MissionRequest(BaseModel):
    entity: str
    filepath: Optional[str] = None

    def model_post_init(self, __context) -> None:
        if not self.entity or not self.entity.strip():
            raise ValueError("Entity name is required")
        if len(self.entity) > 500:
            raise ValueError("Entity name too long (max 500 chars)")

@app.post("/api/mission/start")
async def start_mission(req: MissionRequest):
    if not _check_rate_limit("mission", max_requests=5, window=60.0):
        raise HTTPException(status_code=429, detail="Rate limit: max 5 missions per minute")
    try:
        logger.info(f"Starting assistance mission for entity: {req.entity}, file: {req.filepath}")
        result = await orchestrator.run_mission(req.entity, req.filepath)
        # Forward every orchestrator key the API surface actually uses. We deliberately
        # pass-through instead of cherry-picking so future orchestrator additions (e.g. a new
        # dual-output field) reach the frontend without an endpoint edit each time.
        # NOTE: `entity_name` is renamed to `entity` for API ergonomics — both stay populated
        # for backwards compatibility with older frontends that read `entity_name`.
        forward_keys = {
            "mission_id",
            "entity_name",
            "report",
            "report_markdown",
            "wiki_entry_markdown",
            "wiki_entry_chunk_id",
            "wiki_entry",
            "verified",
            "critic_score",
            "critic_critique",
            "usage",
            "wiki_export",
        }
        forwarded = {k: result[k] for k in forward_keys if k in result}
        forwarded["success"] = True
        forwarded["entity"] = result.get("entity_name", req.entity)
        return forwarded
    except Exception as e:
        logger.error(f"Mission failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class ReviewHarnessRequest(BaseModel):
    auto_commit: bool = False
    commit_message: str = ""

@app.post("/api/harness/run")
async def run_review_harness(req: ReviewHarnessRequest):
    logger.info(f"Review harness run: auto_commit={req.auto_commit}")
    from review_harness import AutonomousReviewHarness
    harness = AutonomousReviewHarness()
    summary = await harness.run()
    if req.auto_commit:
        final = await harness.finalize_and_push(req.commit_message or f"harness: auto-review {summary['tasks_completed']} tasks")
        summary["commit"] = final
    return summary

@app.post("/api/agents/stop")
async def stop_agents():
    orchestrator.stop()
    return {"status": "stopped"}

# ─────────────────────────────────────────────────────────────
# Multi-entity & mission history endpoints
# ─────────────────────────────────────────────────────────────
@app.get("/api/entities")
async def list_entities():
    """List all unique entities with mission/wiki counts, sorted by most recent."""
    try:
        entities = orchestrator.vector_store.list_entities()
        return {"entities": entities, "count": len(entities)}
    except Exception as e:
        logger.error(f"Failed to list entities: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/missions")
async def list_missions(entity: str = "", limit: int = 20):
    """List missions, optionally filtered by entity name. Most recent first."""
    try:
        if entity:
            missions = orchestrator.vector_store.list_missions_for_entity(entity, limit)
        else:
            # Simple: return all missions across all entities
            conn = sqlite3.connect(orchestrator.vector_store.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM missions ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            )
            rows = cursor.fetchall()
            conn.close()
            missions = []
            for row in rows:
                missions.append({
                    "mission_id": row[0],
                    "entity_name": row[1],
                    "status": row[2],
                    "report": row[3],
                    "timestamp": row[4],
                })
        return {"missions": missions, "count": len(missions)}
    except Exception as e:
        logger.error(f"Failed to list missions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ─────────────────────────────────────────────────────────────
# Config endpoint for frontend
# ─────────────────────────────────────────────────────────────
@app.get("/api/config")
async def get_config():
    return {
        "gateway": {
            "openrouter": bool(os.getenv("OPENROUTER_API_KEY")),
            "gemini": bool(os.getenv("GEMINI_API_KEY")),
            "ollama": await gateway._check_ollama(),
        },
        "agents": len(AGENT_DEFS),
        "ws_endpoint": "/api/ws/agents",
    }

@app.get("/api/health/providers")
async def provider_health():
    return await gateway.health()

@app.get("/api/health/usage")
async def usage_health():
    """Return per-mission + session-aggregate LLM usage (tokens + cost)."""
    return gateway.get_all_usage()

@app.get("/api/missions/{mission_id}/cost")
async def mission_cost(mission_id: str):
    """Return usage totals for a specific mission. Empty dict if mission unknown."""
    return gateway.get_mission_usage(mission_id)

# ─────────────────────────────────────────────────────────────
# TASKLIST.md — Source of Truth
# ─────────────────────────────────────────────────────────────
class TaskCreate(BaseModel):
    title: str
    description: str = ""
    priority: str = "medium"
    assigned_to: str = ""
    dependencies: list[str] = []

class TaskUpdate(BaseModel):
    status: str = ""
    priority: str = ""
    assigned_to: str = ""
    linked_node: str = ""
    linked_commit: str = ""
    linked_run: str = ""
    notes: str = ""

@app.get("/api/tasks")
async def get_tasks(status: str = ""):
    if status:
        return task_manager.get_by_status(status)
    return task_manager.get_all()

@app.get("/api/tasks/stats")
async def get_task_stats():
    return task_manager.get_stats()

@app.get("/api/tasks/content")
async def get_tasklist_content():
    return {"content": task_manager.get_content()}

@app.post("/api/tasks")
async def create_task(req: TaskCreate):
    return task_manager.create(req.title, req.description, req.priority, req.assigned_to, req.dependencies)

@app.put("/api/tasks/{task_id}")
async def update_task(task_id: str, req: TaskUpdate):
    kwargs = {k: v for k, v in req.model_dump().items() if v}
    result = task_manager.update(task_id, **kwargs)
    if not result:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return result

@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str):
    if not task_manager.delete(task_id):
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return {"deleted": task_id}

@app.put("/api/tasks/content")
class TaskContentUpdate(BaseModel):
    content: str

@app.put("/api/tasks/content")
async def update_tasklist_content(req: TaskContentUpdate):
    task_manager.update_content(req.content)
    return {"updated": True}

# ─────────────────────────────────────────────────────────────
# Kanban Board
# ─────────────────────────────────────────────────────────────
class KanbanCardCreate(BaseModel):
    task_id: str
    title: str
    agent_id: str = ""
    column: str = "backlog"

class KanbanCardMove(BaseModel):
    column: str

class KanbanCardUpdate(BaseModel):
    branch: str = ""
    file_changes: list[str] = []
    run_id: str = ""
    artifact: str = ""
    blocked_by: str = ""
    notes: str = ""

@app.get("/api/kanban")
async def get_kanban(column: str = ""):
    if column:
        return kanban_board.get_by_column(column)
    return kanban_board.get_all()

@app.get("/api/kanban/stats")
async def get_kanban_stats():
    return kanban_board.get_stats()

@app.post("/api/kanban/sync")
async def sync_kanban_from_tasks():
    tasks = task_manager.get_all()
    kanban_board.sync_from_tasks(tasks)
    return kanban_board.get_all()

@app.post("/api/kanban")
async def create_kanban_card(req: KanbanCardCreate):
    return kanban_board.create(req.task_id, req.title, req.agent_id, req.column)

@app.post("/api/kanban/{card_id}/move")
async def move_kanban_card(card_id: str, req: KanbanCardMove):
    result = kanban_board.move(card_id, req.column)
    if not result:
        raise HTTPException(status_code=404, detail=f"Card {card_id} not found")
    return result

@app.put("/api/kanban/{card_id}")
async def update_kanban_card(card_id: str, req: KanbanCardUpdate):
    kwargs = {k: v for k, v in req.model_dump().items() if v}
    result = kanban_board.update(card_id, **kwargs)
    if not result:
        raise HTTPException(status_code=404, detail=f"Card {card_id} not found")
    return result

@app.delete("/api/kanban/{card_id}")
async def delete_kanban_card(card_id: str):
    if not kanban_board.delete(card_id):
        raise HTTPException(status_code=404, detail=f"Card {card_id} not found")
    return {"deleted": card_id}

# ─────────────────────────────────────────────────────────────
# Run History
# ─────────────────────────────────────────────────────────────
class RunCreate(BaseModel):
    flow_id: str

class RunComplete(BaseModel):
    status: str = "completed"
    error: str = ""
    artifacts: list[str] = []
    commits: list[str] = []

@app.get("/api/history")
async def get_runs(limit: int = 50):
    return run_history.get_all(limit)

@app.get("/api/history/stats")
async def get_history_stats():
    return run_history.get_stats()

@app.get("/api/history/{run_id}")
async def get_run(run_id: str):
    result = run_history.get(run_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return result

@app.post("/api/history")
async def create_run(req: RunCreate):
    run_id = run_history.create(req.flow_id)
    return {"run_id": run_id}

@app.post("/api/history/{run_id}/complete")
async def complete_run(run_id: str, req: RunComplete):
    run_history.complete(run_id, req.status, req.error or None, req.artifacts, req.commits)
    return run_history.get(run_id)

@app.delete("/api/history/{run_id}")
async def delete_run(run_id: str):
    if not run_history.delete(run_id):
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return {"deleted": run_id}

# ─────────────────────────────────────────────────────────────
# Admin: Index + Wiki Vault
# ─────────────────────────────────────────────────────────────

@app.get("/api/admin/index")
async def admin_index():
    """Live snapshot of every store TANGLE uses: SQLite, Qdrant, filesystem.
    Supabase is reported as 'not_connected' — backend integration is Phase 1+ scope
    per AGENTS.md; only the frontend stub exists today.
    """
    # 1. SQLite
    sqlite_info: Dict[str, Any] = {
        "path": str(Path(__file__).parent / "tangle.db"),
        "exists": (Path(__file__).parent / "tangle.db").exists(),
        "wiki_entries_count": 0,
        "missions_count": 0,
        "by_entity": {},
        "oldest_entry": None,
        "newest_entry": None,
    }
    if sqlite_info["exists"]:
        try:
            conn = sqlite3.connect(sqlite_info["path"])
            cur = conn.cursor()
            sqlite_info["wiki_entries_count"] = cur.execute(
                "SELECT COUNT(*) FROM wiki_entries"
            ).fetchone()[0]
            sqlite_info["missions_count"] = cur.execute(
                "SELECT COUNT(*) FROM missions"
            ).fetchone()[0]
            rows = cur.execute(
                "SELECT entity_name, COUNT(*) FROM wiki_entries "
                "GROUP BY entity_name ORDER BY entity_name"
            ).fetchall()
            sqlite_info["by_entity"] = {r[0]: r[1] for r in rows}
            ts_row = cur.execute(
                "SELECT MIN(timestamp), MAX(timestamp) FROM wiki_entries"
            ).fetchone()
            if ts_row and ts_row[0]:
                sqlite_info["oldest_entry"] = ts_row[0]
                sqlite_info["newest_entry"] = ts_row[1]
            conn.close()
        except Exception as e:
            sqlite_info["error"] = str(e)

    # 2. Qdrant
    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    qdrant_info: Dict[str, Any] = {
        "url": qdrant_url,
        "reachable": False,
        "collection": "tangle_wiki_memories",
        "collection_exists": False,
        "points_count": 0,
    }
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            h = await client.get(f"{qdrant_url}/healthz")
            qdrant_info["reachable"] = h.status_code == 200
            if qdrant_info["reachable"]:
                try:
                    c = await client.get(f"{qdrant_url}/collections/tangle_wiki_memories")
                    if c.status_code == 200:
                        qdrant_info["collection_exists"] = True
                        qdrant_info["points_count"] = (
                            c.json().get("result", {}).get("points_count", 0)
                        )
                except Exception:
                    pass
    except Exception as e:
        qdrant_info["error"] = str(e)

    # 3. Supabase — parallel cloud mirror when TANGLE_SUPABASE_ENABLED=1
    supabase_url = os.getenv("SUPABASE_URL", "")
    supabase_key = os.getenv("SUPABASE_ANON_KEY", "")
    supabase_configured = bool(supabase_url and supabase_key)
    supabase_enabled_flag = os.getenv("TANGLE_SUPABASE_ENABLED", "").strip() in ("1", "true", "True")
    supabase_info: Dict[str, Any] = {
        "configured": supabase_configured,
        "enabled": supabase_enabled_flag,
        "status": "not_connected",
        "entries_count": 0,
        "missions_count": 0,
        "by_entity": {},
    }
    if supabase_configured and supabase_enabled_flag:
        try:
            sb_stats = orchestrator.vector_store.get_supabase_stats()
            if sb_stats.get("error"):
                supabase_info["status"] = "error"
                supabase_info["error"] = sb_stats["error"]
            else:
                supabase_info["status"] = "connected"
                supabase_info["entries_count"] = sb_stats["wiki_entries_count"]
                supabase_info["missions_count"] = sb_stats["missions_count"]
                supabase_info["by_entity"] = sb_stats["by_entity"]
        except Exception as e:
            supabase_info["status"] = "error"
            supabase_info["error"] = str(e)

    # 4. Filesystem wiki vault
    fs_info: Dict[str, Any] = {
        "vault_root": str(wiki_vault.vault_root),
        "exists": wiki_vault.vault_root.exists(),
        "files": 0,
        "entities": 0,
        "last_modified": None,
    }
    try:
        c = wiki_vault.count()
        fs_info.update(c)
        if fs_info.get("last_modified"):
            fs_info["last_modified"] = datetime.fromtimestamp(
                fs_info["last_modified"], tz=timezone.utc
            ).isoformat().replace("+00:00", "Z")
    except Exception as e:
        fs_info["error"] = str(e)

    # 5. Uploads directory (raw files)
    uploads_dir = Path(__file__).parent.parent / "uploads"
    uploads_info = {
        "path": str(uploads_dir),
        "exists": uploads_dir.exists(),
        "files": len(list(uploads_dir.glob("*"))) if uploads_dir.exists() else 0,
    }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "sqlite": sqlite_info,
        "qdrant": qdrant_info,
        "supabase": supabase_info,
        "filesystem": fs_info,
        "uploads": uploads_info,
        "stores_healthy": (
            sqlite_info["exists"]
            and (qdrant_info["reachable"] or sqlite_info["wiki_entries_count"] > 0)
        ),
    }

@app.post("/api/admin/export-wiki")
async def admin_export_wiki():
    """Rebuild the Obsidian-compatible wiki vault at docs/wiki/.
    Reads every entry from SQLite, writes per-chunk markdown files with
    YAML frontmatter, plus INDEX / TAGS / _meta and per-entity indexes.

    Safe to call repeatedly — full rebuild every time.
    """
    try:
        return wiki_vault.export_all()
    except Exception as e:
        logger.error(f"Wiki vault export failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/admin/export-wiki/preview")
async def admin_export_wiki_preview():
    """Dry-run: show what export-wiki would do without writing files.
    Useful for sanity-checking before triggering a full rebuild."""
    return wiki_vault.preview_export()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
