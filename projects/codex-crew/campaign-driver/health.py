"""P2 --health: handshake + blocker behave on fixtures."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "common"))
import plant
from core import CampaignDriver, Blocked

HERE = Path(__file__).resolve().parent

def health():
    drv = CampaignDriver({"DUO": "VERIFIED LIVE", "X": "PACKET READY"})
    try:
        drv.promote("DUO", "The DUO: both DRAGGED shirts for $29.99 - saves $9.99 vs buying separately.")
    except Blocked:
        return False
    try:
        drv.promote("X", "clean copy, S-5XL")
        return False
    except Blocked:
        return True

if __name__ == "__main__":
    good = health()
    plant.write_status(HERE, "campaign-driver", "running" if good else "failed",
                       summary="health self-check: handshake + blocker" if good else "health self-check FAILED")
    print("HEALTHY" if good else "UNHEALTHY")
    raise SystemExit(0 if good else 1)
