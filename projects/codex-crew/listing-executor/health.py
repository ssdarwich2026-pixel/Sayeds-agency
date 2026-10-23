"""P4 --health: mock chunk of 3 drains end-to-end and verifies."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "completion-agent"))
sys.path.insert(0, str(HERE.parent / "common"))
import plant
from ledger import Ledger
from packets import Packet
from executor import ListingExecutor, MockAdmin, LaneToken

EV = {"source": "health", "ts": 1, "value": "self-check"}


def health():
    led = Ledger()
    packets = {}
    for i in range(3):
        pf = f"print-{i}.png"
        led.add(pf, f"DESIGN {i}", pf)
        led.transition(pf, "PACKET READY", EV)
        packets[pf] = Packet(key=pf, title=f"DESIGN {i}", print_file=pf,
                             placement="tummy centre ~8.6in")
    rep = ListingExecutor(led, MockAdmin(), packets, LaneToken()).run_chunk()
    return rep["verified"] == ["print-0.png", "print-1.png", "print-2.png"]


if __name__ == "__main__":
    good = health()
    plant.write_status(HERE, "listing-executor", "running" if good else "failed",
                       summary="health self-check: mock chunk of 3 verified"
                       if good else "health self-check FAILED")
    print("HEALTHY" if good else "UNHEALTHY")
    raise SystemExit(0 if good else 1)
