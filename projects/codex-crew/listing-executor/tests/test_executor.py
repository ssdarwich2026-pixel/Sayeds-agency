"""P4 cage tests (C29's set): 10-pack drain, duplicate refusal,
invalid packet refusal, hard-crash resume without double-listing,
blocked retry after unblock, single-lane exclusivity."""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "completion-agent"))
from ledger import Ledger
from packets import Packet
from executor import ListingExecutor, MockAdmin, LaneToken, LaneBusy, AdminError

EV = {"source": "test", "ts": 1, "value": "x"}


def stocked(n=10):
    led = Ledger()
    packets = {}
    for i in range(n):
        pf = f"print-{i:02d}.png"
        led.add(pf, f"DESIGN {i:02d}", pf)
        led.transition(pf, "PACKET READY", EV)
        packets[pf] = Packet(key=pf, title=f"DESIGN {i:02d}", print_file=pf,
                             placement="tummy centre ~8.6in")
    return led, packets


class TestDrain(unittest.TestCase):
    def test_ten_pack_drain_all_verified(self):
        led, packets = stocked(10)
        admin = MockAdmin()
        rep = ListingExecutor(led, admin, packets, LaneToken()).run_chunk()
        self.assertEqual(len(rep["verified"]), 10)
        self.assertEqual(led.counts()["VERIFIED LIVE"], 10)
        self.assertEqual(len(admin.created), 10)

    def test_duplicate_attempt_refused_never_recreated(self):
        led, packets = stocked(3)
        admin = MockAdmin(existing=[("DESIGN 01", "print-01.png")])
        rep = ListingExecutor(led, admin, packets, LaneToken()).run_chunk()
        self.assertNotIn("print-01.png", admin.created)
        self.assertEqual(led.entries["print-01.png"].state, "BLOCKED")
        self.assertIn("duplicate", led.entries["print-01.png"].blocked_reason)
        self.assertEqual(len(rep["verified"]), 2)

    def test_invalid_packet_refused_and_blocked(self):
        led, packets = stocked(2)
        from decimal import Decimal
        packets["print-00.png"].price = Decimal("9.99")  # invented price
        rep = ListingExecutor(led, MockAdmin(), packets, LaneToken(),
                              file_exists=lambda p: False).run_chunk()
        self.assertEqual(rep["verified"], [])
        self.assertEqual(led.entries["print-00.png"].state, "BLOCKED")

    def test_missing_print_file_refused(self):
        led, packets = stocked(1)
        rep = ListingExecutor(led, MockAdmin(), packets, LaneToken(),
                              file_exists=lambda p: False).run_chunk()
        self.assertEqual(rep["refused"][0][0], "print-00.png")
        self.assertIn("does not exist", rep["refused"][0][1][0])


class CrashAdmin(MockAdmin):
    def __init__(self, crash_on):
        super().__init__()
        self.crash_on = crash_on
        self.armed = True

    def create(self, packet):
        if self.armed and packet.print_file == self.crash_on:
            raise RuntimeError("simulated process crash")
        return super().create(packet)


class TestResume(unittest.TestCase):
    def test_hard_crash_resume_no_double_list(self):
        led, packets = stocked(10)
        admin = CrashAdmin("print-04.png")
        ex = ListingExecutor(led, admin, packets, LaneToken())
        with self.assertRaises(RuntimeError):
            ex.run_chunk()
        self.assertEqual(led.counts()["VERIFIED LIVE"], 4)
        admin.armed = False
        rep = ex.run_chunk()
        self.assertEqual(len(rep["verified"]), 6)
        self.assertEqual(led.counts()["VERIFIED LIVE"], 10)
        self.assertEqual(len(admin.created), 10)  # nothing created twice
        self.assertEqual(len(set(admin.created)), 10)

    def test_admin_error_blocks_then_unblock_retries(self):
        led, packets = stocked(2)
        admin = MockAdmin()
        admin.fail_on = {"print-00.png"}
        ex = ListingExecutor(led, admin, packets, LaneToken())
        ex.run_chunk()
        self.assertEqual(led.entries["print-00.png"].state, "BLOCKED")
        admin.fail_on = set()
        led.unblock("print-00.png", EV)
        rep = ex.run_chunk()
        self.assertEqual(rep["verified"], ["print-00.png"])


class TestLane(unittest.TestCase):
    def test_lane_token_is_exclusive(self):
        tok = LaneToken()
        tok.acquire()
        with self.assertRaises(LaneBusy):
            tok.acquire()
        tok.release()
        tok.acquire()  # reusable after release


if __name__ == "__main__":
    unittest.main()
