import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import backends
import envsafe
from fixer import Fixer

BUGGY = "def total(prices, rate):\n    return sum(prices) * rate\n"
TEST = ("import unittest\nfrom pricing import total\n\n"
        "class T(unittest.TestCase):\n"
        "    def test_tax(self):\n"
        "        self.assertEqual(total([100.0], 0.08), 108.0)\n")
GOOD_DIFF = ("--- a/pricing.py\n+++ b/pricing.py\n@@ -1,2 +1,2 @@\n"
             " def total(prices, rate):\n"
             "-    return sum(prices) * rate\n"
             "+    return sum(prices) * (1 + rate)\n")
WRONG_DIFF = ("--- a/pricing.py\n+++ b/pricing.py\n@@ -1,2 +1,2 @@\n"
              " def total(prices, rate):\n"
              "-    return sum(prices) * rate\n"
              "+    return sum(prices) * rate * 2\n")


def make_repo(d):
    (d / "pricing.py").write_text(BUGGY)
    (d / "test_pricing.py").write_text(TEST)
    (d / "INTENT.md").write_text("Intent: total ADDs tax on top of subtotal.\n")
    for args in (["init", "-q"], ["add", "-A"],
                 ["-c", "user.email=t@t", "-c", "user.name=t",
                  "commit", "-qm", "base"]):
        subprocess.run(["git", *args], cwd=str(d), check=True,
                       capture_output=True)


class TestEnvSafe(unittest.TestCase):
    def test_strips_ipv6_keeps_hosts(self):
        env = {"NO_PROXY": "localhost,[::1],fd8b:4f84::1,example.com,::1"}
        self.assertEqual(envsafe.sanitize_env(env)["NO_PROXY"],
                         "localhost,example.com")

    def test_hazards_listed(self):
        env = {"no_proxy": "[::1],localhost"}
        self.assertEqual(len(envsafe.hazards(env)), 1)


class TestExtractDiff(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(backends.extract_diff(GOOD_DIFF), GOOD_DIFF)

    def test_fenced_with_prose(self):
        text = "Here is the fix:\n```diff\n" + GOOD_DIFF + "```\nDone."
        self.assertEqual(backends.extract_diff(text), GOOD_DIFF)

    def test_essay_is_not_a_fix(self):
        self.assertIsNone(backends.extract_diff("You should change line 2."))
        self.assertIsNone(backends.extract_diff(""))


class TestFixerLoop(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.d = Path(self._td.name)
        make_repo(self.d)

    def tearDown(self):
        self._td.cleanup()

    def test_mock_backend_fixes(self):
        rep = Fixer(self.d, backends.MockBackend([GOOD_DIFF]),
                    "python3 -m unittest", max_attempts=2).run()
        self.assertEqual(rep.status, "FIXED")
        self.assertIn("(1 + rate)", (self.d / "pricing.py").read_text())
        self.assertIn("(1 + rate)", rep.diff)
        self.assertEqual(rep.attempts, 1)

    def test_wrong_diff_restores_checkpoint(self):
        rep = Fixer(self.d, backends.MockBackend([WRONG_DIFF]),
                    "python3 -m unittest", max_attempts=3).run()
        self.assertIn(rep.status, ("FAILED", "NO-PROGRESS"))
        # cage discipline: workdir restored, bug intact, nothing claimed
        self.assertEqual((self.d / "pricing.py").read_text(), BUGGY)
        self.assertEqual(rep.diff, WRONG_DIFF)

    def test_backend_timeout_surfaces(self):
        def slow(_ctx):
            raise backends.BackendTimeout("backend exceeded 1s and was killed")
        rep = Fixer(self.d, backends.ScriptedBackend(slow),
                    "python3 -m unittest", max_attempts=3).run()
        self.assertEqual(rep.status, "TIMEOUT")
        self.assertEqual((self.d / "pricing.py").read_text(), BUGGY)

    def test_backend_error_surfaces(self):
        def boom(_ctx):
            raise backends.BackendError("endpoint said: free tier refused")
        rep = Fixer(self.d, backends.ScriptedBackend(boom),
                    "python3 -m unittest", max_attempts=3).run()
        self.assertEqual(rep.status, "BACKEND-ERROR")
        self.assertIn("free tier refused", " ".join(rep.log))

    def test_unparseable_diff_never_applied(self):
        rep = Fixer(self.d, backends.MockBackend(["just an essay"]),
                    "python3 -m unittest", max_attempts=2).run()
        self.assertIn(rep.status, ("FAILED", "NO-PROGRESS"))
        self.assertEqual((self.d / "pricing.py").read_text(), BUGGY)


if __name__ == "__main__":
    unittest.main()
