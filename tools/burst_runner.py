#!/usr/bin/env python3
"""
burst_runner.py - execute ONE job from a burst batch manifest.

Runs identically on a GitHub Actions ubuntu runner and on the local
VM (drain_local.py imports it by path). Self-contained: stdlib plus
Pillow for image_convert (the workflow pip-installs it; if Pillow is
missing, that job fails honestly as a per-item error, nothing else).

Job types (v1 - all in-repo inputs, no network, no external APIs):
  benchmark     - delegates to tools/burst-benchmark.py beside this
                  file's repo (falls back to a sibling copy), reads
                  its result JSON back as the read-back proof.
  image_convert - PNG/JPG/WebP resize/convert with Pillow.
  hash_manifest - sha256 + size for a set of in-repo files/globs.
  text_pack     - deterministic text generation from a template and
                  a list of records (captions, cards, packs).

Failure model (checkpointed-bulk-operations):
  - A job that itself fails -> result JSON with status "error" and
    the exception text; the runner still exits 0, so its artifact
    uploads and the batch summary can record the per-item error.
    One bad job never kills the batch.
  - A manifest/index problem is infrastructure, not an item: the
    runner exits 2 with NO result file, so the failure is visible
    as a dead run rather than a fake per-item error.

Usage:
  burst_runner.py --manifest batches/<batch-id>.json --index N
                  [--out burst-result-N.json] [--workdir .]
Outputs from file-producing jobs land under <workdir>/burst_out/<job_id>/.
"""
import argparse, glob, hashlib, json, os, re, subprocess, sys, time
from pathlib import Path

JOB_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
BATCH_ID_RE = re.compile(r"^batch-[0-9]{8}-[0-9]{3}$")
MAX_JOBS = 256


def validate_manifest(manifest):
    """One validator for setup + runner (P4). Raises ValueError with a
    plain message on any structural problem; returns the manifest."""
    if not isinstance(manifest, dict):
        raise ValueError("manifest is not an object")
    bid = manifest.get("batch_id")
    if not isinstance(bid, str) or not BATCH_ID_RE.match(bid):
        raise ValueError(f"bad batch_id: {bid!r}")
    jobs = manifest.get("jobs")
    if not isinstance(jobs, list) or not jobs:
        raise ValueError("manifest jobs must be a non-empty list")
    if len(jobs) > MAX_JOBS:
        raise ValueError(f"too many jobs: {len(jobs)} > {MAX_JOBS}")
    seen = set()
    for j in jobs:
        if not isinstance(j, dict):
            raise ValueError("job is not an object")
        jid = j.get("id")
        if not isinstance(jid, str) or not JOB_ID_RE.match(jid) \
                or ".." in jid:
            raise ValueError(f"bad job id: {jid!r}")
        if jid in seen:
            raise ValueError(f"duplicate job id: {jid}")
        seen.add(jid)
        if j.get("type") not in HANDLERS:
            raise ValueError(f"job {jid}: unknown type {j.get('type')!r}")
        if not isinstance(j.get("params", {}), dict):
            raise ValueError(f"job {jid}: params must be an object")
    return manifest


def out_dir(workdir, job_id):
    d = Path(workdir) / "burst_out" / job_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def job_benchmark(job, workdir):
    p = job.get("params", {})
    script = Path(workdir) / "tools" / "burst-benchmark.py"
    if not script.exists():
        script = Path(__file__).resolve().with_name("burst-benchmark.py")
    tmp_out = out_dir(workdir, job["id"]) / "benchmark-result.json"
    cmd = [sys.executable, str(script),
           "--iterations", str(p.get("iterations", 20)),
           "--chunk-mb", str(p.get("chunk_mb", 5)),
           "--shard", str(p.get("shard", 0)),
           "--out", str(tmp_out)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    if r.returncode != 0:
        raise RuntimeError(f"benchmark script failed: {r.stderr[-500:]}")
    data = json.loads(tmp_out.read_text())
    return {"benchmark": data["results"],
            "result_file": str(tmp_out.relative_to(workdir))}


def job_image_convert(job, workdir):
    from PIL import Image
    p = job.get("params", {})
    src = (Path(workdir) / p["input"]).resolve()
    if not src.is_relative_to(Path(workdir).resolve()):
        raise ValueError(f"input escapes workdir: {p['input']}")
    if not src.exists():
        raise FileNotFoundError(f"input not in repo: {p['input']}")
    fmt = p.get("format", "jpg").lower()
    if fmt == "jpeg":  # P1: normalize once - the save map has no jpeg key
        fmt = "jpg"
    if fmt not in ("jpg", "png", "webp"):
        raise ValueError(f"unsupported format: {fmt!r}")
    ext = {"jpg": ".jpg", "png": ".png", "webp": ".webp"}[fmt]
    name = p.get("output_name") or (src.stem + ext)
    if "/" in name or "\\" in name or ".." in name:
        raise ValueError(f"bad output_name: {name!r}")
    dst = out_dir(workdir, job["id"]) / name
    im = Image.open(src)
    orig = im.size
    if p.get("width") and p.get("height"):
        im = im.resize((int(p["width"]), int(p["height"])))
    elif p.get("max_width") or p.get("max_height"):
        mw = int(p.get("max_width") or 10 ** 9)
        mh = int(p.get("max_height") or 10 ** 9)
        im.thumbnail((mw, mh))
    if fmt == "jpg" and im.mode not in ("RGB", "L"):
        im = im.convert("RGB")
    im.save(dst, format={"jpg": "JPEG", "png": "PNG",
                          "webp": "WEBP"}[fmt])
    return {"input": p["input"], "output": str(dst.relative_to(workdir)),
            "format": fmt, "size_in": list(orig),
            "size_out": list(im.size), "bytes_out": dst.stat().st_size}


def job_hash_manifest(job, workdir):
    p = job.get("params", {})
    entries, missing = [], []
    seen = set()
    for pat in p["paths"]:
        matched_files = 0
        for f in sorted(glob.glob(str(Path(workdir) / pat), recursive=True)):
            fp = Path(f)
            if fp.is_file() and str(fp) not in seen:
                seen.add(str(fp))
                matched_files += 1
                h = hashlib.sha256(fp.read_bytes()).hexdigest()
                entries.append({"path": str(fp.relative_to(workdir)),
                                "sha256": h, "bytes": fp.stat().st_size})
        # P8: a pattern counts as matched only if it matched >= 1 FILE
        # (a directory-only glob used to read as a silent empty success).
        if matched_files == 0:
            missing.append(pat)
    # require_all now defaults TRUE for our manifests; a job that wants
    # best-effort semantics must say "require_all": false explicitly.
    if missing and p.get("require_all", True):
        raise FileNotFoundError(f"patterns matched no files: {missing}")
    mpath = out_dir(workdir, job["id"]) / "manifest.json"
    mpath.write_text(json.dumps({"job_id": job["id"], "entries": entries},
                                indent=1))
    out = {"files": len(entries), "missing_patterns": missing,
           "manifest_file": str(mpath.relative_to(workdir))}
    if len(entries) <= 100:
        out["entries"] = entries
    return out


def job_text_pack(job, workdir):
    p = job.get("params", {})
    template = p["template"]
    records = p["records"]
    d = out_dir(workdir, job["id"])
    # P5: compute every (name, text) pair BEFORE writing anything, so a
    # collision is a clean per-item error, never a half-written pack.
    pairs = []
    for i, rec in enumerate(records):
        text = template.format(**rec)
        fname = p.get("file_pattern", "item-{i:02d}.txt").format(i=i, **rec)
        pairs.append((fname, text))
    names = [n for n, _ in pairs]
    if len(set(names)) != len(names):
        raise ValueError(f"text_pack filename collision: {sorted(names)}")
    if "pack.txt" in names:
        raise ValueError("text_pack record name 'pack.txt' is reserved")
    files = []
    combined = []
    for fname, text in pairs:
        fp = d / fname
        fp.write_text(text if text.endswith("\n") else text + "\n")
        files.append(str(fp.relative_to(workdir)))
        combined.append(text)
    pack = d / "pack.txt"
    pack.write_text("\n---\n".join(combined) + "\n")
    return {"records": len(records), "files": files,
            "pack_file": str(pack.relative_to(workdir))}


HANDLERS = {"benchmark": job_benchmark, "image_convert": job_image_convert,
            "hash_manifest": job_hash_manifest, "text_pack": job_text_pack}


def run_one(manifest, index, workdir):
    job = manifest["jobs"][index]
    t0 = time.perf_counter()
    base = {"job_id": job["id"], "type": job["type"],
            "batch_id": manifest["batch_id"], "index": index}
    try:
        handler = HANDLERS[job["type"]]
    except KeyError:
        return {**base, "status": "error",
                "error": f"unknown job type: {job['type']}",
                "metrics": {"elapsed_s": 0.0}}
    try:
        outputs = handler(job, Path(workdir))
        return {**base, "status": "ok", "outputs": outputs,
                "metrics": {"elapsed_s": round(time.perf_counter() - t0, 3)}}
    except Exception as e:
        return {**base, "status": "error",
                "error": f"{type(e).__name__}: {e}",
                "metrics": {"elapsed_s": round(time.perf_counter() - t0, 3)}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--index", type=int, required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--workdir", default=".")
    args = ap.parse_args()
    try:
        manifest = validate_manifest(
            json.loads(Path(args.manifest).read_text()))
        if not 0 <= args.index < len(manifest["jobs"]):
            raise ValueError(
                f"index {args.index} out of range "
                f"0..{len(manifest['jobs']) - 1}")
    except Exception as e:
        print(f"INFRASTRUCTURE ERROR: cannot load manifest/index: {e}",
              file=sys.stderr)
        return 2
    result = run_one(manifest, args.index, args.workdir)
    out = args.out or f"burst-result-{args.index}.json"
    # P7: atomic write - a killed runner never leaves a torn result.
    tmp = f"{out}.tmp"
    Path(tmp).write_text(json.dumps(result, indent=1))
    os.replace(tmp, out)
    print(json.dumps(result, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
