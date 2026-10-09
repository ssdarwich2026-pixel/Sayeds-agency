#!/usr/bin/env python3
"""Standalone uniqueness gate for Foxwatch candidates.

Usage: python3 uniqueness_gate.py --new-dir candidates/ --collection-dir ../artwork/
Exit 0 = all new files pass. Exit 1 = a duplicate/near-duplicate was found.
Checks: SHA-256 byte-identity + perceptual dHash (hamming <= 5) against every
file in the collection dir and among the new files themselves.
"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from foxwatch_pipeline import sha256_of, dhash, hamming

def hashes(d):
    out = {}
    for fn in sorted(os.listdir(d)):
        if fn.lower().endswith(".png"):
            p = os.path.join(d, fn)
            out[fn] = (sha256_of(p), dhash(p))
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--new-dir", required=True)
    ap.add_argument("--collection-dir", required=True)
    ap.add_argument("--threshold", type=int, default=5)
    a = ap.parse_args()
    coll, new = hashes(a.collection_dir), hashes(a.new_dir)
    coll_sha = {h for h, _ in coll.values()}
    fails = []
    seen = {}
    for fn, (sh, dh) in new.items():
        if sh in coll_sha:
            fails.append(f"{fn}: byte-identical to a collection piece"); continue
        for cfn, (csh, cdh) in coll.items():
            if hamming(dh, cdh) <= a.threshold:
                fails.append(f"{fn}: near-duplicate of {cfn} (dhash {hamming(dh, cdh)})")
        for sfn, (ssh, sdh) in seen.items():
            if sh == ssh: fails.append(f"{fn}: byte-identical to {sfn} (same batch)")
            elif hamming(dh, sdh) <= a.threshold: fails.append(f"{fn}: near-duplicate of {sfn} (same batch)")
        seen[fn] = (sh, dh)
    for f in fails: print("FAIL:", f)
    print(f"checked={len(new)} failed={len(fails)}")
    return 1 if fails else 0

if __name__ == "__main__":
    sys.exit(main())
