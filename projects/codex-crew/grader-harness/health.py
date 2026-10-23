"""P3 --health: imports + a known PASS and a known FAIL must grade right."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "common"))
import grader, plant

HERE = Path(__file__).resolve().parent

def health():
    ok_pass = grader.grade("The DUO: both DRAGGED shirts for $29.99 - save $9.99 vs buying separately.")["verdict"] == "PASS"
    ok_fail = grader.grade("Limited edition - 20% off for the first 100 creators!")["verdict"] == "FAIL"
    return ok_pass and ok_fail

if __name__ == "__main__":
    good = health()
    plant.write_status(HERE, "grader-harness", "running" if good else "failed",
                       summary="health self-check: PASS fixture passes, FAIL fixture fails" if good else "health self-check FAILED")
    print("HEALTHY" if good else "UNHEALTHY")
    raise SystemExit(0 if good else 1)
