"""P1 --health: modules import + a full state walk succeeds."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "common"))
import plant
from ledger import Ledger
import queue as chunk_queue

HERE = Path(__file__).resolve().parent
EV = {"source": "health", "ts": 1, "value": "self-check"}

def health():
    led = Ledger()
    led.add("selfcheck", "SELFCHECK", "selfcheck.png")
    led.transition("selfcheck", "PACKET READY", EV)
    led.transition("selfcheck", "LISTED UNVERIFIED", EV)
    led.transition("selfcheck", "VERIFIED LIVE", EV)
    a = chunk_queue.finish_audit(led, target=1)
    return a["done"] is True

if __name__ == "__main__":
    good = health()
    plant.write_status(HERE, "completion-agent", "running" if good else "failed",
                       summary="health self-check: state walk + audit" if good else "health self-check FAILED")
    print("HEALTHY" if good else "UNHEALTHY")
    raise SystemExit(0 if good else 1)
