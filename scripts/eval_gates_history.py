#!/usr/bin/env python3
"""TANGLE eval gates — history wrapper.

Runs scripts/eval_gates.py, parses results, appends to a JSONL history file,
and surfaces a regression flag if any gate fails. Designed to run from launchd
daily and let external monitoring (or a Telegram bot later) read the flag.

Output:
  ~/.tangle-eval-history.jsonl   one line per day, all gates from that run
  ~/.tangle-eval-latest.json     latest run snapshot (overwritten each time)
  ~/.tangle-eval-regression.txt  present if any gate FAILed (empty file = signal)

Exit codes:
  0  all gates PASS
  1  one or more FAIL
  2  eval_gates.py couldn't run at all

Usage:
  backend/venv/bin/python scripts/eval_gates_history.py
  backend/venv/bin/python scripts/eval_gates_history.py --skip 7   # skip slow E2E
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HISTORY_DIR = Path.home()
HISTORY_FILE = HISTORY_DIR / ".tangle-eval-history.jsonl"
LATEST_FILE = HISTORY_DIR / ".tangle-eval-latest.json"
REGRESSION_FLAG = HISTORY_DIR / ".tangle-eval-regression.txt"


def parse_results(stdout: str) -> list[dict]:
    """Parse eval_gates.py stdout for per-gate results.

    Looks for lines like:
      ✓ G1 Health      PASS     0.06s  (backend=up, supabase=connected ...)
    or ✗ / ~ for FAIL / SKIP.
    """
    pattern = re.compile(r"^\s*[✓✗~]\s+(G\d+\s+\S+)\s+(PASS|FAIL|SKIP)\s+([0-9.]+)s\s*(?:\((.+)\))?")
    results = []
    for line in stdout.split("\n"):
        m = pattern.match(line)
        if m:
            results.append({
                "gate": m.group(1).strip(),
                "status": m.group(2),
                "dt_seconds": float(m.group(3)),
                "note": (m.group(4) or "").strip(),
            })
    return results


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--skip", type=str, default="", help="Pass through to eval_gates.py")
    args = p.parse_args()

    cmd = [
        "backend/venv/bin/python",
        "scripts/eval_gates.py",
    ]
    if args.skip:
        cmd += ["--skip", args.skip]

    when = datetime.now(timezone.utc).isoformat()
    print(f"Running: {' '.join(cmd)}")
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(Path(__file__).resolve().parent.parent))
    print(proc.stdout)
    if proc.stderr:
        print("STDERR:", proc.stderr, file=sys.stderr)

    results = parse_results(proc.stdout)
    if not results:
        print("ERROR: could not parse any gate results — eval_gates.py output changed?", file=sys.stderr)
        return 2

    # Build the snapshot
    snapshot = {
        "when": when,
        "exit_code": proc.returncode,
        "results": results,
    }
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    skipped = sum(1 for r in results if r["status"] == "SKIP")

    # Append to history
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    with HISTORY_FILE.open("a") as f:
        f.write(json.dumps(snapshot) + "\n")
    LATEST_FILE.write_text(json.dumps(snapshot, indent=2))

    # Regression flag
    if failed:
        REGRESSION_FLAG.write_text(
            f"{when}  {failed} gate(s) failed (out of {len(results)}).\n"
            f"Snapshot: {LATEST_FILE}\n"
            f"History:  {HISTORY_FILE}\n"
        )
        print(f"\n!!! REGRESSION — {failed} gate(s) failed !!!")
        print(f"Flag file: {REGRESSION_FLAG}")
        return 1

    if REGRESSION_FLAG.exists():
        REGRESSION_FLAG.unlink()
    print(f"\n✓ All {passed} gates PASSED — history appended")
    return 0


if __name__ == "__main__":
    sys.exit(main())
