"""Tests for manifest.py + verifier.py (P1 build-out, Agent 81 2026-10-23)."""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import manifest as manifest_mod
import verifier as verifier_mod
from ledger import Ledger, LedgerError

PACKETS_CSV = (
    "drain_order,group,title_exact,print_file,print_file_exists,price_usd,compare_at_usd,sizes,status\n"
    "24,Paris,NOIR VEIL,paris-series/a.png,True,19.99,36.99,S-5XL,READY\n"
    "25,Paris,PARIS IN SMOKE,paris-series/b.png,True,19.99,36.99,S-5XL,READY\n"
    ",Paris,NO PRINTFILE,,True,19.99,36.99,S-5XL,READY\n"
)
DRAIN_CSV = (
    "group,name,print_file,provenance,status\n"
    "Paris,SANS BEGAYER,paris-series/c.png,Paris,TODO\n"
    "Paris,BLUE SCARF,paris-series/d.png,Paris,TODO\n"
)

EV = {"source": "test", "ts": 1, "value": "x"}


class TestManifest(unittest.TestCase):
    def test_packets_rows_land_packet_ready(self):
        ledger, warnings = manifest_mod.build_ledger(PACKETS_CSV)
        self.assertEqual(ledger.counts()["PACKET READY"], 2)
        self.assertEqual(len(warnings), 1)  # the no-print_file row is named, not dropped silently
        self.assertIn("no print_file", warnings[0])

    def test_drain_rows_land_not_started(self):
        ledger, warnings = manifest_mod.build_ledger(DRAIN_CSV)
        self.assertEqual(ledger.counts()["NOT STARTED"], 2)
        self.assertEqual(warnings, [])

    def test_duplicate_print_file_raises(self):
        dup = DRAIN_CSV + "Paris,SANS BEGAYER,paris-series/c.png,Paris,TODO\n"
        with self.assertRaises(LedgerError):
            manifest_mod.build_ledger(dup)

    def test_unknown_dialect_raises(self):
        with self.assertRaises(ValueError):
            manifest_mod.build_ledger("a,b\n1,2\n")

    def test_real_packets_file_loads_113(self):
        p = Path("/home/hatch/workspace/goals/fourthwall-print-on-demand-shirt-launch"
                 "/hidden_files/blitz-listing-2026-10-23-0941/packets-remaining.csv")
        ledger, warnings = manifest_mod.load_ledger(p)
        self.assertEqual(ledger.counts()["total"], 113)
        self.assertEqual(ledger.counts()["PACKET READY"], 113)


class TestVerifier(unittest.TestCase):
    def _ledger(self):
        ledger = Ledger()
        for key, title in (("a.png", "ALPHA"), ("b.png", "BETA"), ("c.png", "GAMMA")):
            ledger.add(key, title, key)
            ledger.transition(key, "PACKET READY", EV)
        ledger.transition("a.png", "LISTED UNVERIFIED", EV)
        ledger.transition("a.png", "VERIFIED LIVE", EV)
        return ledger

    def test_consistent(self):
        r = verifier_mod.verify_storefront(self._ledger(), ["ALPHA"])
        self.assertTrue(r["consistent"])
        self.assertEqual(r["confirmed"], ["a.png"])

    def test_claimed_not_seen_named_by_key(self):
        r = verifier_mod.verify_storefront(self._ledger(), [])
        self.assertFalse(r["consistent"])
        self.assertEqual(r["claimed_not_seen"], ["a.png"])

    def test_seen_not_claimed_named(self):
        r = verifier_mod.verify_storefront(self._ledger(), ["ALPHA", "MYSTERY TITLE"])
        self.assertFalse(r["consistent"])
        self.assertEqual(r["seen_not_claimed"], [{"key": None, "title": "MYSTERY TITLE"}])

    def test_seen_but_not_verified_named(self):
        r = verifier_mod.verify_storefront(self._ledger(), ["ALPHA", "BETA"])
        self.assertEqual(r["seen_not_claimed"], [{"key": "b.png", "title": "BETA"}])


if __name__ == "__main__":
    unittest.main()
