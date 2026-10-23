"""P2 tests: handshake (VERIFIED LIVE only), grader blocker on
Wave 1 fail patterns, featured order, mock full-day build."""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core import CampaignDriver, Blocked, PLATFORMS

GOOD = "The DUO: both DRAGGED shirts for $29.99 - saves $9.99 vs buying separately. Sizes S-5XL."
BAD = "Limited edition DUO discount - 20% off with code SHIP10, worldwide shipping!"

class TestHandshake(unittest.TestCase):
    def setUp(self):
        self.drv = CampaignDriver({"53 SANS-BEGAYER": "VERIFIED LIVE",
                                   "54 BLUE-SCARF": "PACKET READY",
                                   "DUO": "VERIFIED LIVE"})
    def test_verified_live_promotes(self):
        p = self.drv.promote("53 SANS-BEGAYER", GOOD)
        self.assertEqual(p["design"], "53 SANS-BEGAYER")

    def test_packet_ready_never_promotes(self):
        with self.assertRaises(Blocked) as cm:
            self.drv.promote("54 BLUE-SCARF", GOOD)
        self.assertEqual(cm.exception.failures[0]["rule"], "not-verified-live")

    def test_unknown_design_never_promotes(self):
        with self.assertRaises(Blocked):
            self.drv.promote("GHOST", GOOD)

class TestBlocker(unittest.TestCase):
    def test_wave1_fail_copy_blocks(self):
        drv = CampaignDriver({"DUO": "VERIFIED LIVE"})
        with self.assertRaises(Blocked) as cm:
            drv.promote("DUO", BAD)
        rules = [f["rule"] for f in cm.exception.failures]
        self.assertIn("scarcity-stock", rules)
        self.assertIn("invented-discount", rules)

class TestDay(unittest.TestCase):
    def test_mock_day_builds_all_platforms_featured_first(self):
        drv = CampaignDriver({"53 SANS-BEGAYER": "VERIFIED LIVE", "DUO": "VERIFIED LIVE"})
        drv.promote("DUO", GOOD)
        drv.promote("53 SANS-BEGAYER", "53 SANS-BEGAYER - $19.99 blitz, S-5XL, filmed in Lille, France, 17 Oct 2026.")
        day = drv.build_day()
        self.assertEqual(len(day), len(PLATFORMS))
        self.assertEqual(day[0]["design"], "53 SANS-BEGAYER")
        self.assertTrue(all(d["link"].startswith("https://") for d in day))

if __name__ == "__main__":
    unittest.main()
