"""P1 unit + integration tests: state machine, chunk math, audit,
and the drift case (ledger vs storefront disagreement flagged)."""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ledger import Ledger, LedgerError
import queue as chunk_queue

EV = {"source": "test", "ts": 1, "value": "x"}

def stocked(n=25):
    led = Ledger()
    for i in range(n):
        led.add(f"d{i:02d}", f"DESIGN {i}", f"print-{i}.png")
        led.transition(f"d{i:02d}", "PACKET READY", EV)
    return led

class TestLedger(unittest.TestCase):
    def test_happy_path_to_verified(self):
        led = stocked(1)
        led.transition("d00", "LISTED UNVERIFIED", EV)
        led.transition("d00", "VERIFIED LIVE", EV)
        self.assertEqual(led.counts()["VERIFIED LIVE"], 1)

    def test_illegal_jump_rejected(self):
        led = stocked(1)
        with self.assertRaises(LedgerError):
            led.transition("d00", "VERIFIED LIVE", EV)  # skips LISTED

    def test_evidence_required(self):
        led = Ledger(); led.add("a", "A", "a.png")
        with self.assertRaises(LedgerError):
            led.transition("a", "PACKET READY", None)

    def test_block_unblock_roundtrip(self):
        led = stocked(1)
        led.block("d00", "print file missing", EV)
        self.assertEqual(led.entries["d00"].state, "BLOCKED")
        led.unblock("d00", EV)
        self.assertEqual(led.entries["d00"].state, "PACKET READY")

    def test_chunk_math(self):
        led = stocked(25)
        c1 = chunk_queue.next_chunk(led)
        self.assertEqual(len(c1), 10)
        for k in c1:
            led.transition(k, "LISTED UNVERIFIED", EV)
            led.transition(k, "VERIFIED LIVE", EV)
        self.assertEqual(len(chunk_queue.next_chunk(led)), 10)

    def test_audit_not_done_names_remaining(self):
        led = stocked(3)
        led.transition("d00", "LISTED UNVERIFIED", EV)
        led.transition("d00", "VERIFIED LIVE", EV)
        a = chunk_queue.finish_audit(led, target=3)
        self.assertFalse(a["done"])
        self.assertEqual(sorted(a["remaining"]), ["d01", "d02"])

    def test_audit_done(self):
        led = stocked(2)
        for k in ("d00", "d01"):
            led.transition(k, "LISTED UNVERIFIED", EV)
            led.transition(k, "VERIFIED LIVE", EV)
        self.assertTrue(chunk_queue.finish_audit(led, target=2)["done"])

    def test_drift_flagged_by_name(self):
        # storefront (evidence source) disagrees: d01 never verified
        led = stocked(2)
        led.transition("d00", "LISTED UNVERIFIED", EV)
        led.transition("d00", "VERIFIED LIVE", EV)
        a = chunk_queue.finish_audit(led, target=2)
        self.assertEqual(a["remaining"], ["d01"])

if __name__ == "__main__":
    unittest.main()
