"""P15 --health: modules import + a mock end-to-end fix succeeds."""
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "common"))
import plant
import backends
import envsafe
from fixer import Fixer

BUGGY = "def total(prices, rate):\n    return sum(prices) * rate\n"
TEST = ("import unittest\nfrom pricing import total\n\n"
        "class T(unittest.TestCase):\n"
        "    def test_tax(self):\n"
        "        self.assertEqual(total([100.0], 0.08), 108.0)\n")
DIFF = ("--- a/pricing.py\n+++ b/pricing.py\n@@ -1,2 +1,2 @@\n"
        " def total(prices, rate):\n"
        "-    return sum(prices) * rate\n"
        "+    return sum(prices) * (1 + rate)\n")


def health():
    if envsafe.sanitize_env({"NO_PROXY": "[::1],localhost"})["NO_PROXY"] != "localhost":
        return False
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "pricing.py").write_text(BUGGY)
        (d / "test_pricing.py").write_text(TEST)
        (d / "INTENT.md").write_text("total must ADD tax on top.\n")
        for args in (["init", "-q"], ["add", "-A"],
                     ["-c", "user.email=h@t", "-c", "user.name=h",
                      "commit", "-qm", "base"]):
            subprocess.run(["git", *args], cwd=str(d), check=True,
                           capture_output=True)
        rep = Fixer(d, backends.MockBackend([DIFF]),
                    "python3 -m unittest", max_attempts=1).run()
        return rep.status == "FIXED"


if __name__ == "__main__":
    good = health()
    plant.write_status(HERE, "fixer-agent", "running" if good else "failed",
                       summary="health self-check: mock end-to-end fix"
                       if good else "health self-check FAILED")
    print("HEALTHY" if good else "UNHEALTHY")
    raise SystemExit(0 if good else 1)
