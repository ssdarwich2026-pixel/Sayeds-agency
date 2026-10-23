"""P5 sandbox tests: full day publish+verify, dedupe rerun, grader
block never published, non-live design refused, wrong link /
unknown platform / missing media refused, platform error blocks
then retry succeeds, published-but-hidden blocked, crash-resume
verifies without reposting, journal persistence across instances,
single-lane exclusivity."""
import sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from executor import (SocialPostingExecutor, MockPlatform, Journal,
                      LaneToken, LaneBusy)
from payloads import payload_key, STORE_LINK

COPY = "The DUO: both DRAGGED shirts for $29.99 - saves $9.99 vs buying separately. S-5XL."
STATES = {"DUO": "VERIFIED LIVE", "GHOST": "PACKET READY"}


def day(platforms=("instagram-1", "instagram-2", "facebook")):
    return [{"platform": p, "design": "DUO", "copy": COPY, "link": STORE_LINK}
            for p in platforms]


def make(platform=None, journal=None):
    return SocialPostingExecutor(platform or MockPlatform(),
                                 journal if journal is not None else Journal(),
                                 ledger_states=STATES)


class TestPublish(unittest.TestCase):
    def test_full_day_all_verified(self):
        platform = MockPlatform()
        rep = make(platform).post_day(day())
        self.assertEqual(len(rep["verified"]), 3)
        self.assertEqual(len(platform.published), 3)

    def test_rerun_never_double_posts(self):
        platform = MockPlatform()
        ex = make(platform)
        ex.post_day(day())
        rep = ex.post_day(day())
        self.assertEqual(len(rep["skipped_duplicate"]), 3)
        self.assertEqual(len(platform.published), 3)

    def test_grader_fail_copy_never_published(self):
        platform = MockPlatform()
        bad = [{"platform": "instagram-1", "design": "DUO",
                "copy": "20% off, limited edition, use code SHIP10!",
                "link": STORE_LINK}]
        rep = make(platform).post_day(bad)
        self.assertEqual(rep["verified"], [])
        self.assertEqual(platform.published, [])
        self.assertEqual(len(rep["refused"]), 1)

    def test_non_verified_live_design_refused(self):
        bad = [{"platform": "instagram-1", "design": "GHOST",
                "copy": COPY, "link": STORE_LINK}]
        rep = make().post_day(bad)
        self.assertEqual(rep["verified"], [])
        self.assertIn("VERIFIED LIVE", rep["refused"][0][1][0])

    def test_wrong_link_and_unknown_platform_refused(self):
        bad = [{"platform": "myspace", "design": "DUO", "copy": COPY,
                "link": "https://example.com"}]
        rep = make().post_day(bad)
        errs = rep["refused"][0][1]
        self.assertTrue(any("unknown platform" in e for e in errs))
        self.assertTrue(any("store link" in e for e in errs))

    def test_missing_media_refused(self):
        bad = [{"platform": "instagram-1", "design": "DUO", "copy": COPY,
                "link": STORE_LINK, "media": "/nope/missing.jpg"}]
        ex = SocialPostingExecutor(MockPlatform(), Journal(),
                                   ledger_states=STATES,
                                   file_exists=lambda p: False)
        rep = ex.post_day(bad)
        self.assertEqual(rep["verified"], [])
        self.assertIn("media file does not exist", rep["refused"][0][1][0])


class CrashPlatform(MockPlatform):
    """Publishes the first payload, then raises a hard RuntimeError
    (process crash, not a platform error) on the second."""
    def __init__(self):
        super().__init__()
        self.calls = 0
        self.armed = True

    def publish(self, payload):
        self.calls += 1
        if self.armed and self.calls == 2:
            raise RuntimeError("simulated process crash")
        return super().publish(payload)


class TestFailuresAndResume(unittest.TestCase):
    def test_platform_error_blocks_then_retry_posts(self):
        platform = MockPlatform()
        payloads = day(("instagram-1",))
        key = payload_key(payloads[0])
        platform.fail_on = {key}
        ex = make(platform)
        rep = ex.post_day(payloads)
        self.assertEqual(rep["verified"], [])
        self.assertEqual(ex.journal.state_of(key), "BLOCKED")
        platform.fail_on = set()
        rep2 = ex.retry_blocked(payloads)
        self.assertEqual(rep2["verified"], [key])
        self.assertEqual(len(platform.published), 1)

    def test_published_but_hidden_is_blocked_not_claimed(self):
        platform = MockPlatform()
        payloads = day(("instagram-1",))
        platform.hide_on = {payload_key(payloads[0])}
        rep = make(platform).post_day(payloads)
        self.assertEqual(rep["posted"], [payload_key(payloads[0])])
        self.assertEqual(rep["verified"], [])
        self.assertEqual(len(rep["blocked"]), 1)

    def test_hard_crash_resume_no_double_post(self):
        with tempfile.TemporaryDirectory() as td:
            jpath = Path(td) / "journal.jsonl"
            platform = CrashPlatform()
            payloads = day(("instagram-1", "instagram-2", "facebook"))
            ex = SocialPostingExecutor(platform, Journal(jpath),
                                       ledger_states=STATES)
            with self.assertRaises(RuntimeError):
                ex.post_day(payloads)
            self.assertEqual(len(platform.published), 1)
            # new executor + journal re-read from disk = process restart
            platform.armed = False
            ex2 = SocialPostingExecutor(platform, Journal(jpath),
                                        ledger_states=STATES)
            rep = ex2.post_day(payloads)
            self.assertEqual(len(rep["verified"]), 2)
            self.assertEqual(len(rep["skipped_duplicate"]), 1)
            self.assertEqual(len(platform.published), 3)
            self.assertEqual(len(set(platform.published)), 3)

    def test_unverified_journal_entry_resumes_by_verifying(self):
        platform = MockPlatform()
        payloads = day(("instagram-1",))
        key = payload_key(payloads[0])
        platform.publish(payloads[0])  # published before the "crash"
        journal = Journal()
        journal.record(key, "PUBLISHED_UNVERIFIED", platform.posts[key]["id"])
        ex = SocialPostingExecutor(platform, journal, ledger_states=STATES)
        rep = ex.post_day(payloads)
        self.assertEqual(rep["verified"], [key])
        self.assertEqual(len(platform.published), 1)  # not re-published


class TestLane(unittest.TestCase):
    def test_lane_token_is_exclusive(self):
        tok = LaneToken()
        tok.acquire()
        with self.assertRaises(LaneBusy):
            tok.acquire()
        tok.release()
        tok.acquire()


if __name__ == "__main__":
    unittest.main()
