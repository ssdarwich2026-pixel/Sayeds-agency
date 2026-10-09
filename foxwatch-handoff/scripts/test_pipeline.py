#!/usr/bin/env python3
"""Automated tests for foxwatch_pipeline.py. Run: python3 test_pipeline.py -v"""
import csv
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from foxwatch_pipeline import norm_record, dhash, hamming, sha256_of

from PIL import Image


def make_png(path, color):
    Image.new("RGB", (64, 64), color).save(path)


class TestNormRecord(unittest.TestCase):
    def test_accepts_both_key_styles(self):
        rec, probs = norm_record(
            {"file": "a.png", "name": "N", "description": "D",
             "traits": [{"trait_type": "T", "value": "V"}],
             "price_tier": "standard"}, 0)
        self.assertEqual(probs, [])
        self.assertEqual(rec["tier"], "standard")

        rec2, probs2 = norm_record(
            {"image": "b.png", "name": "N2", "description": "D2",
             "attributes": [{"trait_type": "T", "value": "V"}],
             "tier": "premium", "price_eth": 0.01}, 1)
        self.assertEqual(probs2, [])
        self.assertEqual(rec2["price_eth"], 0.01)

    def test_missing_fields_reported_not_invented(self):
        rec, probs = norm_record({"file": "a.png"}, 0)
        self.assertTrue(any("missing name" in p for p in probs))
        self.assertTrue(any("missing description" in p for p in probs))
        self.assertTrue(any("traits" in p for p in probs))
        self.assertIsNone(rec["name"])  # not invented

    def test_duplicate_trait_type_flagged(self):
        rec, probs = norm_record(
            {"file": "a.png", "name": "N", "description": "D",
             "traits": [{"trait_type": "T", "value": "1"},
                        {"trait_type": "T", "value": "2"}]}, 0)
        self.assertTrue(any("duplicate trait_type" in p for p in probs))


class TestDuplicates(unittest.TestCase):
    def test_sha256_distinguishes_files(self):
        with tempfile.TemporaryDirectory() as d:
            p1, p2 = os.path.join(d, "a.png"), os.path.join(d, "b.png")
            make_png(p1, (255, 0, 0))
            make_png(p2, (255, 0, 0))
            self.assertEqual(sha256_of(p1), sha256_of(p2))  # identical bytes
            make_png(p2, (0, 255, 0))
            self.assertNotEqual(sha256_of(p1), sha256_of(p2))

    def test_dhash_similar_vs_different(self):
        with tempfile.TemporaryDirectory() as d:
            p1, p2, p3 = (os.path.join(d, x) for x in ("a.png", "b.png", "c.png"))
            make_png(p1, (200, 100, 50))
            make_png(p2, (200, 100, 50))
            img = Image.new("RGB", (64, 64))
            px = img.load()
            for x in range(64):
                for y in range(64):
                    # decreasing left-to-right => all dhash bits 1 (vs all 0 for solid)
                    px[x, y] = (255 - x * 4, 255 - y * 2, 128)
            img.save(p3)
            self.assertEqual(hamming(dhash(p1), dhash(p2)), 0)
            self.assertGreater(hamming(dhash(p1), dhash(p3)), 5)


class TestEndToEnd(unittest.TestCase):
    def test_full_run_two_artworks(self):
        import subprocess
        with tempfile.TemporaryDirectory() as d:
            art = os.path.join(d, "art")
            os.makedirs(art)
            make_png(os.path.join(art, "fox1.png"), (255, 0, 0))
            make_png(os.path.join(art, "fox2.png"), (0, 0, 255))
            meta = [
                {"file": "fox1.png", "name": "Alpha", "description": "First",
                 "traits": [{"trait_type": "Mood", "value": "Bold"}],
                 "price_tier": "standard"},
                {"file": "fox2.png", "name": "Beta", "description": "Second",
                 "traits": [{"trait_type": "Mood", "value": "Calm"}],
                 "price_tier": "premium"},
            ]
            mp = os.path.join(d, "meta.json")
            json.dump(meta, open(mp, "w"))
            out = os.path.join(d, "out")
            script = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "foxwatch_pipeline.py")
            r = subprocess.run(
                [sys.executable, script, "--art-dir", art, "--metadata", mp,
                 "--out-dir", out],
                capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            with open(os.path.join(out, "listing-manifest.csv")) as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 2)
            by_name = {x["name"]: x for x in rows}
            # premium-first deterministic numbering
            self.assertEqual(by_name["Beta"]["id"], "FW-001")
            self.assertEqual(by_name["Alpha"]["id"], "FW-002")
            self.assertEqual(by_name["Beta"]["price_eth"], "0.01")
            self.assertEqual(by_name["Alpha"]["price_eth"], "0.005")


if __name__ == "__main__":
    unittest.main()
