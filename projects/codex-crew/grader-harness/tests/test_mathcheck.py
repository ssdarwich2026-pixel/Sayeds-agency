"""Tests for mathcheck.py + scoreboard.py (P3 build-out, Agent 81 2026-10-23)."""
import sys, tempfile, time, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "common"))
import mathcheck, scoreboard


class TestMathCheck(unittest.TestCase):
    def test_real_facts_all_pass(self):
        self.assertTrue(mathcheck.all_pass(), mathcheck.run_checks())

    def test_savings_claims(self):
        self.assertTrue(mathcheck.verify_savings_claim("9.99"))
        self.assertTrue(mathcheck.verify_savings_claim("41.99"))
        self.assertFalse(mathcheck.verify_savings_claim("32.00"))  # Wave 1 invented figure
        self.assertFalse(mathcheck.verify_savings_claim("abc"))


class TestScoreboard(unittest.TestCase):
    def test_collect_flags_stale_names_project(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            import plant
            d = root / "demo"
            d.mkdir()
            plant.write_status(d, "demo", "building", tests_passed=3, tests_failed=0)
            # rewind the file's timestamp by editing its json
            import json
            p = d / "status.json"
            data = json.loads(p.read_text()); data["ts"] = int(time.time()) - 9999
            p.write_text(json.dumps(data))
            board = scoreboard.collect(root, max_age_s=1800)
            self.assertEqual(len(board), 1)
            self.assertEqual(board[0]["project"], "demo")
            self.assertTrue(board[0]["stale"])
            self.assertIn("STALE", scoreboard.render(board))


if __name__ == "__main__":
    unittest.main()
