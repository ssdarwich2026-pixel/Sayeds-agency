"""P5 --health: a mock day of 3 posts publishes, verifies, and a
re-run posts nothing twice."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "common"))
import plant
from executor import SocialPostingExecutor, MockPlatform, Journal
from core import STORE_LINK  # noqa: E402  (campaign-driver on path via payloads)

COPY = "The DUO: both DRAGGED shirts for $29.99 - saves $9.99 vs buying separately. S-5XL."


def _payloads():
    return [{"platform": p, "design": "DUO", "copy": COPY, "link": STORE_LINK}
            for p in ("instagram-1", "instagram-2", "facebook")]


def health():
    platform = MockPlatform()
    ex = SocialPostingExecutor(platform, Journal(),
                               ledger_states={"DUO": "VERIFIED LIVE"})
    rep = ex.post_day(_payloads())
    if len(rep["verified"]) != 3:
        return False
    rep2 = ex.post_day(_payloads())
    return len(rep2["skipped_duplicate"]) == 3 and len(platform.published) == 3


if __name__ == "__main__":
    good = health()
    plant.write_status(HERE, "social-posting-executor", "running" if good else "failed",
                       summary="health self-check: mock day of 3 verified, rerun deduped"
                       if good else "health self-check FAILED")
    print("HEALTHY" if good else "UNHEALTHY")
    raise SystemExit(0 if good else 1)
