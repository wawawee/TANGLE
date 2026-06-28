from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import psutil
import platform
import subprocess
import signal
import os, json, shutil
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("tangle.api")

load_dotenv()

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

gateway = FreeGateway()
orchestrator = AgentOrchestrator(gateway)
langgraph_engine = LangGraphEngine(gateway, orchestrator=orchestrator)
langgraph_engine.compile()
task_manager = TaskListManager()
kanban_board = KanbanBoard()
run_history = RunHistory()

app = FastAPI(title="TANGLE Agentic API")

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
    try:
        logger.info(f"Uploading file {file.filename} for entity {entity}")
        uploads_dir = Path(__file__).parent.parent / "uploads"
        uploads_dir.mkdir(exist_ok=True)
        file_path = uploads_dir / file.filename
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        parsed_data = await orchestrator.ingest(str(file_path), entity)
        return {
            "success": True,
            "filename": file.filename,
            "filepath": str(file_path),
            "parsed": parsed_data
        }
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class MissionRequest(BaseModel):
    entity: str
    filepath: Optional[str] = None

@app.post("/api/mission/start")
async def start_mission(req: MissionRequest):
    try:
        logger.info(f"Starting assistance mission for entity: {req.entity}, file: {req.filepath}")
        result = await orchestrator.run_mission(req.entity, req.filepath)
        return {
            "success": True,
            "mission_id": result["mission_id"],
            "entity": result["entity_name"],
            "report": result["report"],
            "wiki_entry": result["wiki_entry"]
        }
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
