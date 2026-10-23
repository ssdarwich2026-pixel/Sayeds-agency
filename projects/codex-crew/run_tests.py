#!/usr/bin/env python3
"""Run every project suite, write each project's status.json from
the REAL result, print one honest summary. This is the harness
entry the plant + checker use. Usage: python3 run_tests.py"""
import subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "common"))
import plant  # noqa: E402

PROJECTS = ["completion-agent", "campaign-driver", "grader-harness"]

def main():
    results = {}
    for name in PROJECTS:
        pdir = ROOT / name
        proc = subprocess.run([sys.executable, "-m", "unittest", "discover",
                               "-s", str(pdir / "tests"), "-v"],
                              capture_output=True, text=True, cwd=str(pdir))
        out = proc.stdout + proc.stderr
        ran = 0
        for line in out.splitlines():
            if line.startswith("Ran "):
                ran = int(line.split()[1])
        failed = 0 if proc.returncode == 0 else None
        # count failures/errors from the unittest summary lines
        import re
        m = re.search(r"failures=(\d+)", out)
        e = re.search(r"errors=(\d+)", out)
        nfail = (int(m.group(1)) if m else 0) + (int(e.group(1)) if e else 0)
        passed = ran - nfail
        plant.write_status(pdir, name, "building", tests_passed=passed,
                           tests_failed=nfail,
                           summary=f"unittest discover: {passed} passed, {nfail} failed (of {ran})")
        results[name] = (passed, nfail, ran)
        print(f"{name}: {passed} passed, {nfail} failed (of {ran})")
    total_fail = sum(r[1] for r in results.values())
    print("ALL GREEN" if total_fail == 0 else "FAILURES PRESENT")
    return 0 if total_fail == 0 else 1

if __name__ == "__main__":
    raise SystemExit(main())
