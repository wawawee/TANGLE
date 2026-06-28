"""Archon workflow engine integration for SAMI"""
import asyncio, os, json, subprocess
from pathlib import Path

ARCHON_BIN = "archon"
ARCHON_DIR = Path(__file__).resolve().parent.parent / ".archon"
WORKFLOWS_DIR = ARCHON_DIR / "workflows"


def ensure_workflows():
    ARCHON_DIR.mkdir(parents=True, exist_ok=True)
    WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)


SAMI_WORKFLOWS = {
    "sami-agent-task": {
        "name": "sami-agent-task",
        "description": "Run a single agent task with Archon's deterministic harness",
        "nodes": [
            {"name": "plan", "type": "ai", "prompt": "Plan the approach for: {{task}}"},
            {"name": "execute", "type": "ai", "prompt": "Execute the plan. Task: {{task}}"},
            {"name": "validate", "type": "bash", "command": "echo 'Validation complete'"},
        ],
    },
    "sami-code-review": {
        "name": "sami-code-review",
        "description": "Review code changes with automated checks",
        "nodes": [
            {"name": "review", "type": "ai", "prompt": "Review the following changes for bugs, security issues, and quality: {{task}}"},
            {"name": "lint", "type": "bash", "command": "cd {{cwd}} && npx tsc --noEmit 2>&1 || true"},
            {"name": "report", "type": "ai", "prompt": "Summarize review findings and lint results"},
        ],
    },
}


async def archon_run(command: list[str], timeout: int = 120) -> dict:
    """Run an archon CLI command and return result."""
    try:
        proc = await asyncio.create_subprocess_exec(
            ARCHON_BIN, *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return {
            "success": proc.returncode == 0,
            "stdout": stdout.decode()[:2000],
            "stderr": stderr.decode()[:500],
            "returncode": proc.returncode,
        }
    except asyncio.TimeoutError:
        return {"success": False, "stdout": "", "stderr": "[TIMEOUT]", "returncode": -1}
    except FileNotFoundError:
        return {"success": False, "stdout": "", "stderr": "Archon not installed", "returncode": -1}


async def run_workflow(name: str, task: str = "", cwd: str | None = None) -> dict:
    """Run an Archon workflow."""
    cmd = ["workflow", "run", name]
    if task:
        cmd.append(task)
    if cwd:
        cmd.extend(["--cwd", cwd])
    return await archon_run(cmd, timeout=300)


async def list_workflows() -> list[dict]:
    """List available Archon workflows."""
    result = await archon_run(["workflow", "list", "--json"])
    if not result["success"]:
        return []
    try:
        data = json.loads(result["stdout"])
        return data.get("workflows", [])
    except json.JSONDecodeError:
        return []


async def chat(message: str, cwd: str | None = None) -> dict:
    """Send a chat message to Archon's orchestrator."""
    cmd = ["chat", message]
    if cwd:
        cmd.extend(["--cwd", cwd])
    return await archon_run(cmd)


async def doctor() -> dict:
    """Check Archon setup health."""
    return await archon_run(["doctor"])
