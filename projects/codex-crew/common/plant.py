"""PLANT INTERFACE - shared by every codex-crew project (Sayed, 2026-10-23).

Every project must be verifiable like a water plant:
- write_status(): updates status.json on every genuine run
  ({ts, status, tests_passed, tests_failed, last_run_summary}).
  The Micro heartbeat (plant_heartbeat.py, every 5 min) reads the
  mirror of this file under ~/system-agent/codex-crew-status/;
  a stale ts while marked "running" is a fault. Never fake a ts.
- health(): a project is healthy when its modules import and its
  quick self-check passes. health CLIs exit 0 / non-zero.
Stdlib only, $0.
"""
import json, time
from pathlib import Path

STATUSES = ("building", "running", "graduated", "failed")

def write_status(project_dir, project, status, tests_passed=None,
                 tests_failed=None, summary=""):
    if status not in STATUSES:
        raise ValueError(f"unknown status {status!r}")
    project_dir = Path(project_dir)
    project_dir.mkdir(parents=True, exist_ok=True)
    data = {"project": project, "ts": int(time.time()), "status": status,
            "tests_passed": tests_passed, "tests_failed": tests_failed,
            "last_run_summary": summary}
    (project_dir / "status.json").write_text(json.dumps(data, indent=2) + "\n")
    return data

def read_status(project_dir):
    p = Path(project_dir) / "status.json"
    if not p.exists():
        return {"status": "not-yet-shipped"}
    return json.loads(p.read_text())
