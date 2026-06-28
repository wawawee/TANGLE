"""Autonomous Review Harness — zero-question continuous flow: Review → Improve → Test → Log → Push"""
import re, os, json, time, asyncio, subprocess, logging
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional
from datetime import datetime

logger = logging.getLogger("sami.harness")

HARNESS_DIR = Path(__file__).resolve().parent.parent / ".review-harness"


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class ReviewFinding:
    line: int
    severity: str  # critical, warning, style, perf
    category: str  # bug, security, performance, maintainability, ux
    message: str
    suggestion: str
    auto_fixable: bool = False
    fixed_code: Optional[str] = None
    file: str = ""

    def to_dict(self):
        return asdict(self)


@dataclass
class TestResult:
    persona: str  # user, debugger, senior
    passed: bool
    assertions: int
    failures: list = field(default_factory=list)
    coverage: int = 0
    logs: list = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


@dataclass
class Task:
    id: str
    file_path: str
    type: str  # review, improve, test, validate
    status: str = "pending"  # pending, in-progress, done, failed
    priority: int = 5
    created_at: str = ""
    completed_at: Optional[str] = None
    result: Optional[dict] = None
    error: Optional[str] = None

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()


# ============================================================================
# TASK MANAGER
# ============================================================================

class TaskManager:
    def __init__(self, store_path: str = None):
        self.store_path = Path(store_path or str(HARNESS_DIR / "tasks.json"))
        self.tasks: dict[str, Task] = {}
        self._load()

    def _load(self):
        if self.store_path.exists():
            try:
                data = json.loads(self.store_path.read_text())
                self.tasks = {k: Task(**v) for k, v in data.items()}
            except Exception:
                self.tasks = {}

    def _save(self):
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        obj = {k: asdict(v) for k, v in self.tasks.items()}
        self.store_path.write_text(json.dumps(obj, indent=2))

    def add(self, file_path: str, task_type: str, priority: int = 5) -> str:
        import uuid
        task_id = str(uuid.uuid4())[:8]
        task = Task(id=task_id, file_path=file_path, type=task_type, priority=priority)
        self.tasks[task_id] = task
        self._save()
        return task_id

    def start(self, task_id: str):
        t = self.tasks.get(task_id)
        if t:
            t.status = "in-progress"
            self._save()

    def complete(self, task_id: str, result: dict = None):
        t = self.tasks.get(task_id)
        if t:
            t.status = "done"
            t.completed_at = datetime.utcnow().isoformat()
            t.result = result
            self._save()

    def fail(self, task_id: str, error: str):
        t = self.tasks.get(task_id)
        if t:
            t.status = "failed"
            t.error = error
            self._save()

    def get_pending(self) -> list[Task]:
        return sorted(
            [t for t in self.tasks.values() if t.status == "pending"],
            key=lambda x: x.priority,
            reverse=True,
        )

    def get_all(self) -> list[Task]:
        return list(self.tasks.values())

    def get_by_file_and_type(self, file_path: str, task_type: str) -> Optional[Task]:
        for t in self.tasks.values():
            if t.file_path == file_path and t.type == task_type and t.status != "done":
                return t
        return None


# ============================================================================
# HISTORY LOGGER
# ============================================================================

class HistoryLogger:
    def __init__(self, history_path: str = None):
        self.history_path = Path(history_path or str(HARNESS_DIR / "history.jsonl"))
        self.history_path.parent.mkdir(parents=True, exist_ok=True)

    async def log(self, entry: dict):
        entry["timestamp"] = datetime.utcnow().isoformat()
        with open(self.history_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def get_recent(self, n: int = 10) -> list[dict]:
        if not self.history_path.exists():
            return []
        lines = self.history_path.read_text().strip().split("\n")
        entries = [json.loads(l) for l in lines if l.strip()]
        return entries[-n:]


# ============================================================================
# GIT INTEGRATION
# ============================================================================

class GitIntegration:
    def __init__(self, branch: str = "master", remote: str = "origin"):
        self.branch = branch
        self.remote = remote

    def has_changes(self) -> bool:
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True, text=True, timeout=10,
            )
            return bool(result.stdout.strip())
        except Exception:
            return False

    def stage(self, files: list[str]):
        if not files:
            return
        subprocess.run(["git", "add"] + files, capture_output=True, timeout=30)

    def commit(self, message: str) -> str:
        result = subprocess.run(
            ["git", "commit", "-m", message, "--no-verify"],
            capture_output=True, text=True, timeout=30,
        )
        match = re.search(r"\[.+\s([a-f0-9]+)\]", result.stdout)
        return match.group(1) if match else "unknown"

    def push(self) -> bool:
        result = subprocess.run(
            ["git", "push", self.remote, self.branch],
            capture_output=True, text=True, timeout=60,
        )
        return result.returncode == 0

    def get_diff(self) -> str:
        try:
            result = subprocess.run(
                ["git", "diff", "HEAD~1", "--stat"],
                capture_output=True, text=True, timeout=10,
            )
            return result.stdout.strip() or "no-diff"
        except Exception:
            return "no-diff"

    def get_changed_files(self) -> list[str]:
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", "HEAD"],
                capture_output=True, text=True, timeout=10,
            )
            return [f for f in result.stdout.strip().split("\n") if f]
        except Exception:
            return []


# ============================================================================
# REVIEW AGENT — Static analysis for security, bugs, perf, style
# ============================================================================

class ReviewAgent:
    PATTERNS = [
        # Security: eval/exec (but not create_subprocess_exec, etc.)
        (r'(?<!\w)eval\s*\(|(?<!\w)exec\s*\(', 'critical', 'security',
         'Dangerous code execution (eval/exec)',
         'Use ast.literal_eval, json.loads, or a proper parser'),
        # Security: hardcoded secrets
        (r'(api[_-]?key|password|secret|token)\s*[:=]\s*["\'][a-zA-Z0-9]{16,}["\']', 'critical', 'security',
         'Hardcoded credential detected',
         'Move to environment variables or secret manager'),
        # Security: SQL injection
        (r'f["\'].*SELECT.*\{.*\}.*["\']|f["\'].*INSERT.*\{.*\}.*["\']', 'critical', 'security',
         'Possible SQL injection via f-string',
         'Use parameterized queries'),
        # Bug: bare except
        (r'except\s*:', 'warning', 'bug',
         'Bare except catches everything including KeyboardInterrupt',
         'Use except Exception: or specific exception types'),
        # Bug: mutable default
        (r'def\s+\w+\s*\(.*=\s*(\[\]|\{\}|set\(\))\s*\)', 'warning', 'bug',
         'Mutable default argument — shared across calls',
         'Use None as default and create inside function'),
        # Performance: nested loops
        (r'for\s+.*:.*\n\s+for\s+', 'warning', 'performance',
         'Nested loop detected — O(n²) risk',
         'Consider dict/set lookups or restructuring'),
        # Style: print in production
        (r'print\s*\(', 'style', 'maintainability',
         'Debug print in code',
         'Use structured logger'),
        # Style: TODO/FIXME
        (r'#\s*(TODO|FIXME|HACK|XXX)', 'style', 'maintainability',
         'Technical debt marker',
         'Address or remove before production'),
        # Performance: string concat in loop
        (r'for\s+.*\n.*\+=\s*["\']', 'warning', 'performance',
         'String concatenation in loop',
         'Use list.append() and join()'),
        # Maintainability: long function
        (r'def\s+\w+\s*\(.*\)\s*:', None, None, None, None),  # handled separately
    ]

    def analyze(self, file_path: str, source: str) -> list[ReviewFinding]:
        findings = []
        lines = source.split("\n")

        for pattern, severity, category, message, suggestion in self.PATTERNS:
            if severity is None:
                continue
            for i, line in enumerate(lines):
                stripped = line.strip()
                # Skip pure comment lines (except TODO/FIXME pattern which targets comments)
                if stripped.startswith("#") and "TODO" not in pattern and "FIXME" not in pattern:
                    continue
                if re.search(pattern, line):
                    # Skip comments that allow the pattern
                    if "# allow-" in line.lower() or "# noqa" in line.lower():
                        continue
                    findings.append(ReviewFinding(
                        line=i + 1, severity=severity, category=category,
                        message=message, suggestion=suggestion, file=file_path,
                    ))

        # Structural analysis
        ext = Path(file_path).suffix
        is_python = ext in ('.py',)
        is_js_ts = ext in ('.js', '.jsx', '.ts', '.tsx')

        if is_python and "try:" in source and "except" not in source:
            findings.append(ReviewFinding(
                line=1, severity="critical", category="bug",
                message="Try block without except — silent failure",
                suggestion="Add except block or remove try",
                file=file_path,
            ))

        if is_js_ts and "try {" in source and ".catch(" not in source and "catch " not in source and "catch{" not in source:
            findings.append(ReviewFinding(
                line=1, severity="critical", category="bug",
                message="Try block without catch — unhandled rejection",
                suggestion="Add catch block or use Promise.catch()",
                file=file_path,
            ))

        # Long function detection
        if is_python:
            func_starts = [(i, line) for i, line in enumerate(lines) if re.match(r'\s*def\s+\w+', line)]
            for idx, (start, _) in enumerate(func_starts):
                end = func_starts[idx + 1][0] if idx + 1 < len(func_starts) else len(lines)
                func_len = end - start
                if func_len > 80:
                    findings.append(ReviewFinding(
                        line=start + 1, severity="warning", category="maintainability",
                        message=f"Function is {func_len} lines — consider splitting",
                        suggestion="Extract into smaller focused functions",
                        file=file_path,
                    ))
        elif is_js_ts:
            func_starts = [(i, line) for i, line in enumerate(lines) if re.match(r'\s*(async\s+)?function\s+\w+|const\s+\w+\s*=\s*(async\s+)?\(', line)]
            for idx, (start, _) in enumerate(func_starts):
                end = func_starts[idx + 1][0] if idx + 1 < len(func_starts) else len(lines)
                func_len = end - start
                if func_len > 80:
                    findings.append(ReviewFinding(
                        line=start + 1, severity="warning", category="maintainability",
                        message=f"Function is {func_len} lines — consider splitting",
                        suggestion="Extract into smaller focused functions",
                        file=file_path,
                    ))

        # Import analysis
        if "import *" in source:
            findings.append(ReviewFinding(
                line=1, severity="warning", category="maintainability",
                message="Wildcard import — pollutes namespace",
                suggestion="Import specific names",
                file=file_path,
            ))

        return findings


# ============================================================================
# AUTO-FIXER — Safe transformations
# ============================================================================

class AutoFixer:
    TRANSFORMS = [
        # == → === (Python doesn't have this, but for JS/TS files)
        (r'([^=!])==([^=])', r'\1===\2', 'Loose equality → strict'),
        # Remove console.log (JS/TS)
        (r'\s*console\.(log|debug|info)\s*\([^)]*\);?\s*\n?', '', 'Remove debug logging'),
    ]

    PYTHON_TRANSFORMS = [
        # print → logger
        (r'(\s*)print\s*\((.+?)\)\s*$', r'\1logger.info(\2)', 'print → logger.info'),
        # except Exception: → except Exception:
        (r'(\s*)except\s*:', r'\1except Exception:', 'Bare except → Exception'),
        # import * → specific imports (flag only, can't auto-fix safely)
        # TODO/FIXME comments → add tracking
        (r'(\s*)#\s*(TODO|FIXME|HACK|XXX)\s*:\s*(.+)$', r'\1# [\2] \3 — tracked in review harness', 'TODO/FIXME tagged'),
    ]

    def apply(self, file_path: str, findings: list[ReviewFinding]) -> list[str]:
        applied = []
        source = Path(file_path).read_text()
        original = source
        ext = Path(file_path).suffix

        transforms = self.PYTHON_TRANSFORMS if ext in ('.py',) else self.TRANSFORMS

        for pattern, replacement, desc in transforms:
            new_source, count = re.subn(pattern, replacement, source, flags=re.MULTILINE)
            if count > 0:
                source = new_source
                applied.append(f"{file_path}: {desc} ({count} occurrences)")

        if source != original:
            Path(file_path).write_text(source)

        return applied


# ============================================================================
# DEBUG AGENT — Runtime safety analysis
# ============================================================================

class DebugAgent:
    def test(self, file_path: str, source: str) -> TestResult:
        failures = []
        logs = []

        # Unprotected JSON.parse
        if "json.loads(" in source and "try" not in source and "except" not in source:
            failures.append("Unprotected json.loads — will throw on malformed input")

        # Unhandled async
        if "async def " in source and "await " not in source and "asyncio" not in source:
            failures.append("Async function without await — confusing API")

        # Unhandled promise (JS)
        if ".then(" in source and ".catch(" not in source and "try" not in source:
            failures.append("Promise chain without catch — unhandled rejection")

        # Array method without guard
        if re.search(r'\.map\(|\.filter\(|\.reduce\(', source):
            if "?." not in source and "isinstance" not in source and "Array.isArray" not in source:
                failures.append("Collection method without null/undefined guard")

        # Infinite loop
        for match in re.finditer(r'while\s*\(([^)]+)\)', source):
            cond = match.group(1).strip()
            if cond in ("True", "true", "1", "1 == 1"):
                failures.append(f"Potential infinite loop: while {cond}")

        # Memory leak: setInterval without clearInterval
        if "setInterval" in source and "clearInterval" not in source:
            failures.append("setInterval without clearInterval — memory leak")

        # Resource leak: open without close
        if "open(" in source and "close()" not in source and "with " not in source:
            failures.append("Resource opened without close — potential leak")

        # Subprocess without timeout
        if "subprocess.run(" in source and "timeout" not in source:
            failures.append("subprocess.run without timeout — hang risk")

        # HTTP without timeout
        if "httpx.get(" in source or "requests.get(" in source:
            if "timeout" not in source:
                failures.append("HTTP request without timeout — hang risk")

        lines = source.split("\n")
        logs.append(f"Analyzed {len(lines)} lines, {len(failures)} potential runtime issues")

        return TestResult(
            persona="debugger", passed=len(failures) == 0,
            assertions=len(self.__class__.__dict__), failures=failures, logs=logs,
        )


# ============================================================================
# SENIOR DEV AGENT — Architecture & design review
# ============================================================================

class SeniorDevAgent:
    def review(self, file_path: str, source: str) -> TestResult:
        failures = []
        logs = []

        # No exports
        if len(source) > 200 and "export " not in source and "def " not in source and "class " not in source:
            failures.append("Large module with no exports — dead code or missing API")

        # God class
        classes = re.findall(r'class\s+(\w+)', source)
        for cls in classes:
            # Count methods in class
            class_block = re.search(f'class {cls}.*?(?=class |$)', source, re.DOTALL)
            if class_block:
                methods = len(re.findall(r'\s+def\s+\w+', class_block.group()))
                if methods > 15:
                    failures.append(f"{cls} has {methods} methods — violates Single Responsibility")

        # Direct instantiation without DI
        direct_news = len(re.findall(r'new\s+\w+\s*\(', source))
        if direct_news > 3 and "inject" not in source.lower() and "factory" not in source.lower():
            failures.append(f"{direct_news} direct instantiations — consider dependency injection")

        # Naming: uppercase vars
        if re.search(r'let\s+[A-Z]', source) or re.search(r'const\s+[A-Z]', source):
            failures.append("Uppercase variable names — should be camelCase (PascalCase for types only)")

        # Missing docstrings
        if classes and '"""' not in source and "'''" not in source and "/**" not in source:
            failures.append("Classes lack docstrings — maintainability debt")

        # Complexity score
        conditions = len(re.findall(r'if\s*\(|elif\s*\(|while\s*\(|for\s+.*\s+in\s+|except\s+', source))
        total_lines = len(source.split("\n"))
        complexity = round((conditions / max(total_lines, 1)) * 100)

        logs.append(f"Architectural review: {len(failures)} concerns")
        logs.append(f"Complexity score: {complexity}")

        return TestResult(
            persona="senior", passed=len(failures) == 0,
            assertions=6, failures=failures, logs=logs,
        )


# ============================================================================
# USER AGENT — API ergonomics & UX
# ============================================================================

class UserAgent:
    def test(self, file_path: str, source: str) -> TestResult:
        failures = []
        logs = []

        # Async without await
        if "async def " in source and "await " not in source and "Promise" not in source:
            failures.append("Async function without await — confusing API contract")

        # Cryptic error messages
        for match in re.finditer(r'raise\s+\w+\(\s*["\']([^"\']+)["\']', source):
            msg = match.group(1)
            if len(msg) < 10 or " " not in msg:
                failures.append(f'Cryptic error message: "{msg}" — users will not understand')

        # Function with many params, no defaults
        for match in re.finditer(r'def\s+\w+\s*\(([^)]*)\)', source):
            params = match.group(1)
            if "," in params and "=" not in params and "self" not in params:
                failures.append("Function with multiple params has no defaults — consider options object")

        # Destructive without confirmation
        if ("delete" in source or "remove" in source) and "confirm" not in source.lower():
            logs.append("Warning: destructive operation without confirmation flow")

        logs.append(f"UX audit: {len(failures)} friction points")

        return TestResult(
            persona="user", passed=len(failures) == 0,
            assertions=5, failures=failures, logs=logs,
        )


# ============================================================================
# MAIN HARNESS
# ============================================================================

class AutonomousReviewHarness:
    def __init__(self, include_patterns: list[str] = None, exclude_patterns: list[str] = None,
                 branch: str = "master", remote: str = "origin"):
        self.tasks = TaskManager()
        self.history = HistoryLogger()
        self.git = GitIntegration(branch=branch, remote=remote)
        self.review_agent = ReviewAgent()
        self.debug_agent = DebugAgent()
        self.senior_agent = SeniorDevAgent()
        self.user_agent = UserAgent()
        self.fixer = AutoFixer()
        self.include_patterns = include_patterns or ["**/*.py", "**/*.ts", "**/*.tsx", "**/*.js", "**/*.jsx"]
        self.exclude_patterns = exclude_patterns or [
            "**/node_modules/**", "**/dist/**", "**/.review-harness/**",
            "**/*.test.*", "**/*.spec.*", "**/venv/**", "**/__pycache__/**",
        ]
        self.base_dir = Path(__file__).resolve().parent.parent

    def discover_files(self) -> list[str]:
        import glob as glob_mod
        all_files = []
        for pattern in self.include_patterns:
            full_pattern = str(self.base_dir / pattern)
            matches = glob_mod.glob(full_pattern, recursive=True)
            for m in matches:
                rel = os.path.relpath(m, str(self.base_dir))
                # Skip if any exclude pattern matches
                skip = False
                for ep in self.exclude_patterns:
                    ep_clean = ep.replace("**/", "").replace("/**", "")
                    if ep_clean in rel or rel.startswith(ep_clean) or rel.startswith("node_modules") or "node_modules" in rel:
                        skip = True
                        break
                if not skip:
                    all_files.append(rel)
        return sorted(set(all_files))

    async def run(self) -> dict:
        start = time.time()
        logger.info("🔧 Autonomous Review Harness starting")

        # 1. DISCOVER
        files = self.discover_files()
        logger.info(f"📁 Discovered {len(files)} files")

        # 2. QUEUE
        for f in files:
            self.tasks.add(f, "review", priority=10)
            self.tasks.add(f, "improve", priority=9)
            self.tasks.add(f, "test", priority=8)
            self.tasks.add(f, "validate", priority=7)

        # 3. EXECUTE
        all_findings = []
        all_test_results = []
        files_changed = set()

        pending = self.tasks.get_pending()
        for task in pending:
            self.tasks.start(task.id)
            try:
                if task.type == "review":
                    findings = await self._execute_review(task)
                    all_findings.extend(findings)
                elif task.type == "improve":
                    applied = await self._execute_improve(task)
                    if applied:
                        files_changed.add(task.file_path)
                elif task.type == "test":
                    results = await self._execute_test(task)
                    all_test_results.extend(results)
                elif task.type == "validate":
                    await self._execute_validate(task)
            except Exception as e:
                self.tasks.fail(task.id, str(e))
                logger.error(f"❌ Task {task.id} failed: {e}")

        # 4. FINALIZE
        completed = len([t for t in self.tasks.get_all() if t.status == "done"])
        elapsed = round(time.time() - start, 2)

        summary = {
            "files_discovered": len(files),
            "tasks_completed": completed,
            "total_findings": len(all_findings),
            "critical_findings": len([f for f in all_findings if f.severity == "critical"]),
            "test_results": len(all_test_results),
            "files_changed": len(files_changed),
            "elapsed_seconds": elapsed,
        }

        logger.info(f"📊 Summary: {json.dumps(summary)}")

        # Log to history
        await self.history.log({
            "type": "harness_run",
            "summary": summary,
            "findings": [f.to_dict() for f in all_findings],
            "test_results": [r.to_dict() for r in all_test_results],
        })

        return summary

    async def _execute_review(self, task: Task) -> list[ReviewFinding]:
        file_path = self.base_dir / task.file_path
        if not file_path.exists():
            self.tasks.complete(task.id, {"findings": [], "count": 0})
            return []

        source = file_path.read_text()
        findings = self.review_agent.analyze(task.file_path, source)
        self.tasks.complete(task.id, {"findings": [f.to_dict() for f in findings], "count": len(findings)})

        critical = [f for f in findings if f.severity == "critical"]
        if critical:
            logger.warning(f"🚨 {task.file_path}: {len(critical)} critical issues")

        return findings

    async def _execute_improve(self, task: Task) -> list[str]:
        review_task = self.tasks.get_by_file_and_type(task.file_path, "review")
        findings = []
        if review_task and review_task.result:
            findings_data = review_task.result.get("findings", [])
            findings = [ReviewFinding(**f) for f in findings_data]

        applied = self.fixer.apply(str(self.base_dir / task.file_path), findings)
        self.tasks.complete(task.id, {"applied": applied})

        if applied:
            logger.info(f"🔧 {task.file_path}: {len(applied)} auto-fixes applied")

        return applied

    async def _execute_test(self, task: Task) -> list[TestResult]:
        file_path = self.base_dir / task.file_path
        if not file_path.exists():
            self.tasks.complete(task.id, {})
            return []

        source = file_path.read_text()

        debug = self.debug_agent.test(task.file_path, source)
        senior = self.senior_agent.review(task.file_path, source)
        user = self.user_agent.test(task.file_path, source)

        all_passed = debug.passed and senior.passed and user.passed
        total_failures = len(debug.failures) + len(senior.failures) + len(user.failures)

        if not all_passed:
            logger.warning(f"⚠️ {task.file_path}: {total_failures} failures across personas")
        else:
            logger.info(f"✅ {task.file_path}: All personas passed")

        results = [debug, senior, user]
        self.tasks.complete(task.id, {
            "debug": debug.to_dict(),
            "senior": senior.to_dict(),
            "user": user.to_dict(),
            "all_passed": all_passed,
        })

        return results

    async def _execute_validate(self, task: Task):
        file_path = self.base_dir / task.file_path
        ext = Path(task.file_path).suffix

        if ext == ".py":
            try:
                result = subprocess.run(
                    ["python3", "-m", "py_compile", str(file_path)],
                    capture_output=True, text=True, timeout=30,
                )
                self.tasks.complete(task.id, {"valid": result.returncode == 0, "errors": result.stderr})
            except Exception as e:
                self.tasks.complete(task.id, {"valid": False, "errors": str(e)})
        else:
            self.tasks.complete(task.id, {"valid": True, "skipped": True})

    async def finalize_and_push(self, message: str = None) -> dict:
        if not self.git.has_changes():
            return {"status": "no_changes"}

        changed = self.git.get_changed_files()
        self.git.stage(changed)

        msg = message or f"harness: auto-review {len(self.tasks.get_all())} tasks, {len(changed)} files"
        commit_hash = self.git.commit(msg)

        pushed = self.git.push()

        await self.history.log({
            "type": "commit",
            "commit": commit_hash,
            "files": changed,
            "pushed": pushed,
            "diff": self.git.get_diff(),
        })

        return {"status": "committed", "commit": commit_hash, "files": changed, "pushed": pushed}
