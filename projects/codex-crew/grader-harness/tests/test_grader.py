"""P3 regression suite: every Wave 1 fail pattern must FAIL,
every PASS pattern must PASS. (C23's graduation set, as fixtures.)"""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import grader

PASS_COPY = [
    "DRAGGED - The Photograph | SHiPTrOLLYARd. $19.99 while the blitz runs (compare-at $36.99), Gildan Heavyweight, sizes S-5XL.",
    "The DUO: both DRAGGED shirts together for $29.99, Fourthwall store only. Buying separately is $39.98, so the duo saves $9.99 - and $41.99 against the $71.98 compare-at total.",
    "Filmed in Lille, France, 17 Oct 2026. Blitz ends Tue Oct 27, 2026.",
    "Questions on shipping? The store checkout shows the exact options for your address.",
]

FAIL_CASES = {
    "360-discount": ("Get 20% off for the first 100 creators - limited stock, order now!", "invented-discount"),
    "361-limited": ("LIMITED EDITION drop - once it's gone, it's gone.", "scarcity-stock"),
    "362-profit": ("Our profit on each shirt is $10.49, and you save $32.00 vs compare-at with the duo!", "profit-leak"),
    "362-savings": ("DUO deal: save $32.00 vs compare-at today.", "wrong-savings"),
    "364-code": ("Use code SHIP10 at checkout for a surprise.", "invented-code"),
    "364-sizes": ("Available in XS, S, M, L, XL, XXL - worldwide shipping included.", "bad-sizes"),
    "target-live": ("Shop all 156 shirts live now on the store!", "target-as-live"),
    "duo-discount": ("The DUO discount bundle is back at $29.99.", "duo-called-discount"),
}

class TestPassCopy(unittest.TestCase):
    def test_all_pass_copy_passes(self):
        for copy in PASS_COPY:
            with self.subTest(copy=copy[:40]):
                self.assertEqual(grader.grade(copy)["verdict"], "PASS", grader.grade(copy))

class TestWave1Fails(unittest.TestCase):
    def test_each_fail_pattern_fails_with_its_rule(self):
        for name, (copy, rule_name) in FAIL_CASES.items():
            with self.subTest(case=name):
                r = grader.grade(copy)
                self.assertEqual(r["verdict"], "FAIL")
                self.assertIn(rule_name, [f["rule"] for f in r["failures"]])

    def test_failures_quote_the_offending_line(self):
        r = grader.grade("Line one is fine, S-5XL.\nLimited edition, hurry!")
        self.assertEqual(r["failures"][0]["line"], 2)

if __name__ == "__main__":
    unittest.main()
