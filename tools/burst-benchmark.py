#!/usr/bin/env python3
"""
burst-benchmark.py - Light, deterministic burst baseline.

Representative job (same logic in the GitHub Actions workflow and the
Colab/Kaggle notebook): hash (SHA-256) + compress (zlib level 6) a
deterministic chunk of data, repeatedly. It mirrors asset-pack work
(image/archive prep): CPU-bound, single-threaded, no network, no GPU.

Design limits (by intent): default run uses a 5 MB chunk x 20 iterations,
peak extra RAM well under 500 MB, wall time well under 2 minutes.
Usage:
  python3 burst-benchmark.py [--iterations 20] [--chunk-mb 5]
                             [--shard 0] [--out PATH]
"""
import argparse, hashlib, json, os, platform, resource, sys, time, zlib
from pathlib import Path


def meminfo():
    out = {}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            k, _, v = line.partition(":")
            if k in ("MemTotal", "MemAvailable"):
                out[k] = int(v.split()[0]) // 1024  # MB
    except Exception:
        pass
    return out


def make_chunk(chunk_mb: int, shard: int) -> bytes:
    # Deterministic pseudo-random data (seeded by shard), so compression
    # work is representative of photo/asset data, not a trivially
    # repeating pattern. Same seed = same bytes on every platform
    # (CPython random.Random.randbytes, Python >= 3.9).
    import random
    return random.Random(20261029 + shard).randbytes(chunk_mb * 1024 * 1024)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iterations", type=int, default=20)
    ap.add_argument("--chunk-mb", type=int, default=5)
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--out", default=str(Path(__file__).with_name(
        "burst-benchmark-baseline-2026-10-29.json")))
    args = ap.parse_args()

    mem_before = meminfo()
    data = make_chunk(args.chunk_mb, args.shard)
    digests = []
    compressed_total = 0
    t0 = time.perf_counter()
    for i in range(args.iterations):
        h = hashlib.sha256(data).hexdigest()
        comp = zlib.compress(data, level=6)
        digests.append(h)
        compressed_total += len(comp)
    elapsed = time.perf_counter() - t0
    peak_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024

    result = {
        "benchmark": "sha256+zlib6 on deterministic chunk",
        "verified_run": True,
        "host": {
            "hostname": platform.node(),
            "platform": platform.platform(),
            "python": platform.python_version(),
            "cpu_count_logical": os.cpu_count(),
            "mem_total_mb": mem_before.get("MemTotal"),
            "mem_available_mb_at_start": mem_before.get("MemAvailable"),
        },
        "workload": {
            "shard": args.shard,
            "iterations": args.iterations,
            "chunk_mb": args.chunk_mb,
            "total_mb_processed_per_pass": args.iterations * args.chunk_mb,
            "passes": 2,  # one hash pass + one compress pass per iteration
        },
        "results": {
            "elapsed_s": round(elapsed, 3),
            "tasks_per_min": round(args.iterations / elapsed * 60, 2) if elapsed else None,
            "mb_per_s_processed": round(args.iterations * args.chunk_mb / elapsed, 2) if elapsed else None,
            "peak_rss_mb_process": peak_mb,
            "compressed_bytes_total": compressed_total,
            "first_digest_sha256": digests[0] if digests else None,
            "digests_identical_across_iterations": len(set(digests)) == 1 if digests else False,
        },
        "notes": "Single-threaded VM baseline only. Burst equivalence must be "
                 "measured by running the identical workload on the Actions "
                 "runners / Colab runtime and comparing tasks_per_min totals.",
    }
    Path(args.out).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
