"""SCOREBOARD (P3 - one unified code-health board, U5 slice).

Reads every project's status.json via the plant interface and prints
one honest board: per-project status, tests passed/failed, status age.
A project whose ts is older than max_age_s (default 1800) while not
'graduated' is flagged STALE, not guessed healthy. Used by the 15-min
checker and the upgrade windows. Stdlib only.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "common"))
import plant  # noqa: E402

DEFAULT_AGE_S = 1800


def collect(codex_root, max_age_s=DEFAULT_AGE_S, now=None):
    now = int(now if now is not None else time.time())
    root = Path(codex_root)
    board = []
    for child in sorted(root.iterdir()):
        if not child.is_dir() or not (child / "status.json").exists():
            continue
        st = plant.read_status(child)
        age = now - st.get("ts", 0)
        stale = st.get("status") != "graduated" and age > max_age_s
        board.append({
            "project": st.get("project", child.name),
            "status": st.get("status", "?"),
            "tests_passed": st.get("tests_passed"),
            "tests_failed": st.get("tests_failed"),
            "age_s": age,
            "stale": stale,
        })
    return board


def render(board):
    lines = ["project | status | passed/failed | age_s | stale"]
    for b in board:
        lines.append(f"{b['project']} | {b['status']} | "
                     f"{b['tests_passed']}/{b['tests_failed']} | "
                     f"{b['age_s']} | {'STALE' if b['stale'] else 'ok'}")
    green = all(b["tests_failed"] in (0, None) and not b["stale"] for b in board)
    lines.append("ALL GREEN" if green else "NEEDS ATTENTION")
    return "\n".join(lines)


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parent.parent)
    print(render(collect(root)))
