#!/usr/bin/env python3
"""
foxwatch_pipeline.py — reusable Foxwatch NFT preparation pipeline.

What it does (all $0, all local, no network, no wallet):
  1. Matches PNG artwork files to metadata records (by filename).
  2. Validates: unique names, unique files, required fields, well-formed traits,
     sane pricing tiers. NEVER invents missing metadata — gaps are reported.
  3. Detects duplicates: exact byte matches (sha256) + near-duplicates
     (perceptual dHash, PIL only).
  4. Emits a listing manifest CSV + validation report for every eligible artwork.

Usage:
  python3 foxwatch_pipeline.py --art-dir ./art --metadata ./metadata.json \
      --out-dir ./out --exclude 1419648857_Looking_super_cool_for_my_haircut.png

Metadata format accepted (list of objects, flexible keys):
  required: file|filename|image, name, description, traits|attributes
  optional: id, price_tier|tier (standard|premium), price_eth,
            supply, royalty_pct, excluded (true to skip)

Pricing flags (--price-standard, --price-premium, --supply, --royalty) are
PROPOSED values applied only where the record lacks its own price. They are
planning inputs, not on-chain facts. Nothing here mints, lists, or signs.

Exit code: 0 = manifest written (warnings ok), 1 = blocking errors found.
"""

import argparse, csv, hashlib, json, os, sys
from collections import defaultdict

try:
    from PIL import Image
    HAVE_PIL = True
except ImportError:
    HAVE_PIL = False

REQUIRED_PRICE_TIERS = {"standard", "premium"}
SKIP_TIERS = {"skip", "excluded", "exclude", "do-not-list"}


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def dhash(path, size=8):
    """Perceptual difference hash. Returns int bitmask."""
    img = Image.open(path).convert("L").resize((size + 1, size), Image.LANCZOS)
    px = list(img.getdata())
    bits = 0
    for r in range(size):
        for c in range(size):
            bits = (bits << 1) | (1 if px[r * (size + 1) + c] > px[r * (size + 1) + c + 1] else 0)
    return bits


def hamming(a, b):
    return bin(a ^ b).count("1")


def norm_record(raw, idx):
    """Accept flexible key names; return normalized dict + list of problems."""
    probs = []
    g = lambda *ks: next((raw[k] for k in ks if k in raw and raw[k] not in (None, "")), None)
    rec = {
        "src_index": idx,
        "id": g("id") or f"FW-{idx+1:03d}",
        "file": g("file", "filename", "image"),
        "name": g("name"),
        "description": g("description"),
        "traits": g("traits", "attributes") or [],
        "tier": g("price_tier", "tier"),
        "price_eth": g("price_eth"),
        "supply": g("supply"),
        "royalty_pct": g("royalty_pct"),
        "excluded": bool(g("excluded", "skip")),
    }
    if not rec["file"]:
        probs.append("missing file reference")
    if not rec["name"]:
        probs.append("missing name")
    if not rec["description"]:
        probs.append("missing description — NOT invented, must be supplied")
    if not isinstance(rec["traits"], list) or not rec["traits"]:
        probs.append("missing/empty traits — NOT invented, must be supplied")
    else:
        seen_tt = set()
        for t in rec["traits"]:
            tt = t.get("trait_type") if isinstance(t, dict) else None
            vv = t.get("value") if isinstance(t, dict) else None
            if not tt or vv in (None, ""):
                probs.append(f"malformed trait entry: {t}")
            elif tt in seen_tt:
                probs.append(f"duplicate trait_type '{tt}'")
            else:
                seen_tt.add(tt)
    if rec["tier"] and rec["tier"] not in REQUIRED_PRICE_TIERS:
        probs.append(f"unknown price_tier '{rec['tier']}'")
    return rec, probs


def main():
    ap = argparse.ArgumentParser(description="Foxwatch NFT preparation pipeline")
    ap.add_argument("--art-dir", required=True, help="directory of PNG artwork")
    ap.add_argument("--metadata", required=True, help="master metadata JSON (list)")
    ap.add_argument("--out-dir", required=True, help="output directory")
    ap.add_argument("--exclude", default="", help="comma-separated filenames to exclude")
    ap.add_argument("--price-standard", type=float, default=0.005)
    ap.add_argument("--price-premium", type=float, default=0.01)
    ap.add_argument("--supply", type=int, default=100)
    ap.add_argument("--royalty", type=float, default=10.0)
    ap.add_argument("--dhash-threshold", type=int, default=5,
                    help="max hamming distance to flag near-duplicate")
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    excluded = {e.strip() for e in args.exclude.split(",") if e.strip()}
    errors, warnings = [], []

    # ---- load metadata ----
    try:
        raw_meta = json.load(open(args.metadata))
    except Exception as e:
        print(f"FATAL: cannot read metadata: {e}", file=sys.stderr)
        return 1
    if isinstance(raw_meta, dict):
        raw_meta = list(raw_meta.values())
    records = []
    for i, raw in enumerate(raw_meta):
        rec, probs = norm_record(raw if isinstance(raw, dict) else {}, i)
        if rec["excluded"] or (rec["file"] in excluded) or (rec["tier"] in SKIP_TIERS):
            rec["status"] = "excluded"
        else:
            rec["status"] = "ok"
        for p in probs:
            (errors if rec["status"] != "excluded" else warnings).append(f"{rec['id']} ({rec['file']}): {p}")
        records.append(rec)

    # ---- uniqueness ----
    for key in ("name", "file", "id"):
        seen = defaultdict(list)
        for r in records:
            if r[key]:
                seen[r[key]].append(r["id"])
        for val, ids in seen.items():
            if len(ids) > 1:
                errors.append(f"duplicate {key} '{val}' in: {', '.join(ids)}")

    # ---- match files on disk ----
    disk = {}
    for fn in sorted(os.listdir(args.art_dir)):
        if fn.lower().endswith(".png"):
            disk[fn] = os.path.join(args.art_dir, fn)
    meta_files = {r["file"] for r in records if r["file"]}
    for fn in sorted(set(disk) - meta_files):
        warnings.append(f"on disk but no metadata: {fn} (ignored, not listed)")
    for r in records:
        if r["status"] == "excluded":
            continue
        if r["file"] not in disk:
            errors.append(f"{r['id']}: metadata file missing on disk: {r['file']}")
            r["status"] = "missing-file"
        else:
            r["disk_path"] = disk[r["file"]]

    # ---- duplicate detection ----
    hash_groups = defaultdict(list)
    for r in records:
        if r.get("disk_path"):
            try:
                hash_groups[sha256_of(r["disk_path"])].append(r["id"])
            except OSError as e:
                errors.append(f"{r['id']}: cannot hash: {e}")
    for h, ids in hash_groups.items():
        if len(ids) > 1:
            errors.append(f"byte-identical duplicates: {', '.join(ids)} (sha256 {h[:12]}…)")

    if HAVE_PIL:
        hashes = {}
        for r in records:
            if r.get("disk_path"):
                try:
                    hashes[r["id"]] = dhash(r["disk_path"])
                except Exception as e:
                    warnings.append(f"{r['id']}: dhash failed: {e}")
        ids = list(hashes)
        flagged = set()
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                d = hamming(hashes[ids[i]], hashes[ids[j]])
                if d <= args.dhash_threshold and d > 0:
                    pair = tuple(sorted((ids[i], ids[j])))
                    if pair not in flagged:
                        flagged.add(pair)
                        warnings.append(
                            f"near-duplicate artwork (dhash distance {d}): {pair[0]} ~ {pair[1]} — review visually")
    else:
        warnings.append("PIL not installed — perceptual duplicate check skipped (byte-hash check still ran)")

    # ---- pricing (proposed values only where record lacks its own) ----
    for r in records:
        if r["status"] != "ok":
            continue
        if r["price_eth"] in (None, ""):
            if r["tier"] == "premium":
                r["price_eth"] = args.price_premium
            elif r["tier"] == "standard":
                r["price_eth"] = args.price_standard
            else:
                warnings.append(f"{r['id']}: no tier and no price — price left blank, needs decision")
                r["price_eth"] = ""
        if r["supply"] in (None, ""):
            r["supply"] = args.supply
        if r["royalty_pct"] in (None, ""):
            r["royalty_pct"] = args.royalty

    eligible = [r for r in records if r["status"] == "ok"]
    # Deterministic catalog numbering: premium first, then alphabetical.
    # Stable across runs regardless of metadata file order.
    eligible.sort(key=lambda r: (0 if r["tier"] == "premium" else 1, (r["name"] or "").lower()))
    for n, r in enumerate(eligible, 1):
        r["id"] = f"FW-{n:03d}"
    for n, r in enumerate((x for x in records if x["status"] != "ok"), 1):
        r["id"] = f"SKIP-{n:02d}"

    # ---- manifest ----
    man_path = os.path.join(args.out_dir, "listing-manifest.csv")
    with open(man_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "name", "tier", "price_eth", "supply", "royalty_pct",
                    "filename", "sha256", "trait_count", "status"])
        for r in records:
            sha = sha256_of(r["disk_path"])[:16] + "…" if r.get("disk_path") else ""
            w.writerow([r["id"], r["name"], r["tier"], r["price_eth"], r["supply"],
                        r["royalty_pct"], r["file"], sha,
                        len(r["traits"]) if isinstance(r["traits"], list) else 0,
                        r["status"]])

    # ---- report ----
    rep_path = os.path.join(args.out_dir, "validation-report.md")
    with open(rep_path, "w") as f:
        f.write("# Foxwatch pipeline validation report\n\n")
        f.write(f"- Metadata records: {len(records)}\n")
        f.write(f"- Eligible for listing: {len(eligible)}\n")
        f.write(f"- Excluded: {sum(1 for r in records if r['status']=='excluded')}\n")
        f.write(f"- Blocking errors: {len(errors)} | Warnings: {len(warnings)}\n\n")
        if errors:
            f.write("## Errors (must fix)\n\n")
            for e in errors:
                f.write(f"- {e}\n")
            f.write("\n")
        if warnings:
            f.write("## Warnings (review)\n\n")
            for w_ in warnings:
                f.write(f"- {w_}\n")
            f.write("\n")
        f.write("## Notes\n\n")
        f.write("- Prices marked from --price-standard/--price-premium are PROPOSED until Sayed approves per batch.\n")
        f.write("- Nothing here mints, lists, or signs. Signing stays manual in Sayed's wallet.\n")

    print(f"records={len(records)} eligible={len(eligible)} "
          f"errors={len(errors)} warnings={len(warnings)}")
    print(f"manifest: {man_path}")
    print(f"report:   {rep_path}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
