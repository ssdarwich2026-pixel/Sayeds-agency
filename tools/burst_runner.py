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
  render        - Current Bureau video render (v2, 2026-11-02): a
                  faithful port of dayfile/build-dayfile.py's recipe
                  minus its VM-side TTS step - narration audio is a
                  pre-generated in-repo input (the TruthTeller voice
                  service lives on the VM and cannot run here; a job
                  without narration in hand is not burst-ready).
                  Footage may be in-repo files (small fixtures) or
                  public URLs the runner downloads. One sequential
                  encode chain per job (parallelism comes from the
                  matrix, never concurrent encodes inside a job -
                  the Spotlight EP-1 corruption lesson). Outputs the
                  finished mp4 + SRT + thumbnail + measurements.

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
    # "local-drain" is drain_local.py's reserved pseudo-batch id.
    if not isinstance(bid, str) or not (BATCH_ID_RE.match(bid)
                                        or bid == "local-drain"):
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
    chunks = manifest.get("chunks")
    if chunks is not None:
        # Manifest v2 (P12 chunked sharding): chunks partition the job
        # list - every index in exactly one chunk, no empties.
        if not isinstance(chunks, list) or not chunks \
                or len(chunks) > MAX_JOBS:
            raise ValueError("bad chunks list")
        covered = []
        for c in chunks:
            idxs = c.get("job_indices") if isinstance(c, dict) else None
            if not isinstance(idxs, list) or not idxs:
                raise ValueError("chunk without job_indices")
            for ix in idxs:
                if not isinstance(ix, int) or not 0 <= ix < len(jobs):
                    raise ValueError(f"chunk index out of range: {ix!r}")
                covered.append(ix)
        if sorted(covered) != list(range(len(jobs))):
            raise ValueError("chunks must cover every job exactly once")
    return manifest


def out_dir(workdir, job_id):
    # P9 (strengthened per 82 reverify): containment is resolved BEFORE
    # any filesystem operation, and resolve() covers symlink escapes,
    # not just ".." and absolutes. Checked here, at the single choke
    # point every file-producing handler passes through.
    # The RETURNED path keeps the caller's own expression (relative
    # stays relative): handlers report outputs via relative_to(workdir),
    # and returning the resolved absolute form broke exactly that on
    # Batch #4 (workdir "." on the runners) - regression-tested below.
    root = (Path(workdir) / "burst_out").resolve()
    d_res = (root / job_id).resolve()
    if not d_res.is_relative_to(root):
        raise ValueError(f"job id escapes burst_out: {job_id!r}")
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
    wd = Path(workdir).resolve()
    for pat in p["paths"]:
        matched_files = 0
        for f in sorted(glob.glob(str(Path(workdir) / pat), recursive=True)):
            fp = Path(f)
            # P9: never read through a symlink that escapes the workdir.
            if fp.is_file() and str(fp) not in seen \
                    and fp.resolve().is_relative_to(wd):
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


# ---------------------------------------------------------------------
# render (v2) - port of dayfile/build-dayfile.py, TTS replaced by a
# pre-generated narration input. Helpers mirror the builder's own so
# burst output matches the VM press's masters (same zoompan clips,
# same proportional SRT allocator, same drawtext assembly, plus the
# loudnorm normalization pass the press applies to its long masters).
# ---------------------------------------------------------------------

def _sh(cmd, timeout=1800, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True,
                       timeout=timeout, **kw)
    if r.returncode != 0:
        raise RuntimeError(
            f"FAILED: {' '.join(str(c) for c in cmd)}\n{r.stderr[-2000:]}")
    return r


def _probe_dur(ffprobe, path):
    out = _sh([ffprobe, "-v", "error", "-show_entries", "format=duration",
               "-of", "default=noprint_wrappers=1:nokey=1", str(path)])
    return float(out.stdout.strip())


def _repo_file(workdir, rel):
    """Contained in-repo input (same rule as image_convert's input)."""
    src = (Path(workdir) / rel).resolve()
    if not src.is_relative_to(Path(workdir).resolve()):
        raise ValueError(f"input escapes workdir: {rel}")
    if not src.exists():
        raise FileNotFoundError(f"input not in repo: {rel}")
    return src


def _esc(t):
    return t.replace("\\", "\\\\").replace(":", "\\:") \
            .replace("'", "").replace(",", "\\,")


def _split_sentences(text):
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _wrap_cue(sentence, width=42):
    words, lines, cur = sentence.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 <= width:
            cur = (cur + " " + w).strip()
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    cues, buf = [], []
    for ln in lines:
        buf.append(ln)
        if len(buf) == 2:
            cues.append("\n".join(buf))
            buf = []
    if buf:
        cues.append("\n".join(buf))
    return cues


def _srt_time(s):
    h, rem = divmod(int(s), 3600)
    mi, sec = divmod(rem, 60)
    ms = int(round((s - int(s)) * 1000))
    return f"{h:02d}:{mi:02d}:{sec:02d},{ms:03d}"


def _make_srt(script, total_dur, path):
    cues = []
    for sent in _split_sentences(script):
        cues.extend(_wrap_cue(sent))
    total_chars = sum(len(c) for c in cues) or 1
    t, out, idx = 0.4, [], 1
    for c in cues:
        d = max(1.2, total_dur * len(c) / total_chars)
        out.append(f"{idx}\n{_srt_time(t)} --> {_srt_time(t + d)}\n{c}\n")
        t += d + 0.15
        idx += 1
    Path(path).write_text("\n".join(out))
    return path


def _loudnorm_measure(ffmpeg, path):
    """Integrated loudness / true peak of a file via loudnorm analysis.
    Returns (input_i, input_tp) as floats, or (None, None)."""
    r = subprocess.run(
        [ffmpeg, "-v", "info", "-vn", "-i", str(path), "-af",
         "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json",
         "-f", "null", "-"], capture_output=True, text=True, timeout=1800)
    blocks = re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr)
    if not blocks:
        return None, None
    try:
        d = json.loads(blocks[-1])
        return float(d["input_i"]), float(d["input_tp"])
    except Exception:
        return None, None


def job_render(job, workdir):
    import shutil
    import urllib.request
    p = job.get("params", {})
    wd = Path(workdir)
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise RuntimeError("ffmpeg/ffprobe not on PATH on this runner")
    manifest = json.loads(_repo_file(wd, p["manifest"]).read_text())
    item_id = manifest["id"]
    fmt = manifest.get("format", "landscape")
    is_short = fmt in ("short", "short45")
    is_short45 = fmt == "short45"
    VW, VH = (1080, 1920) if is_short else (1920, 1080)
    font_b = str(_repo_file(
        wd, p.get("font_bold", "tools/burst_data/fonts/DejaVuSans-Bold.ttf")))
    font_r = str(_repo_file(
        wd, p.get("font_regular", "tools/burst_data/fonts/DejaVuSans.ttf")))
    AMBER = "0xE8A33D"
    d = out_dir(wd, job["id"])
    work = d / "_work"
    work.mkdir(parents=True, exist_ok=True)

    # 1. narration (pre-generated on the VM press; never synthesized here)
    voice = work / "voice.mp3"
    shutil.copyfile(_repo_file(wd, p["voice"]), voice)
    adur = _probe_dur(ffprobe, voice)
    target = 43.0 if is_short45 else (57.5 if is_short else None)
    if target and adur > target:
        factor = adur / target
        tmp = work / "voice_fast.mp3"
        _sh([ffmpeg, "-y", "-v", "error", "-i", str(voice), "-filter:a",
             f"atempo={factor:.3f}", "-b:a", "128k", str(tmp)])
        os.replace(tmp, voice)
        adur = _probe_dur(ffprobe, voice)

    # 2. footage: in-repo file or public URL; stills become 6 s
    #    slow-zoom clips; video clips normalized + capped at 300 s.
    clips = []
    for i, ft in enumerate(manifest["footage"]):
        url = ft["url"]
        raw = work / f"clip{i}_raw"
        norm = work / f"clip{i}_norm.mp4"
        if re.match(r"^https?://", url):
            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0 (DayFile/1.0)"})
            with urllib.request.urlopen(req, timeout=120) as r, \
                    open(raw, "wb") as f:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
            if raw.stat().st_size < 1024:
                raise RuntimeError(f"download too small: {url}")
        else:
            shutil.copyfile(_repo_file(wd, url), raw)
        if re.search(r"\.(jpe?g|png|webp|gif)(\?|$)", url, re.I):
            _sh([ffmpeg, "-y", "-v", "error", "-loop", "1", "-i", str(raw),
                 "-vf", f"scale={VW}:{VH}:force_original_aspect_ratio="
                        f"increase,crop={VW}:{VH},"
                        f"zoompan=z='min(zoom+0.0012,1.12)':d=180:"
                        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                        f"s={VW}x{VH}:fps=30",
                 "-t", "6", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                 "-preset", "veryfast", str(norm)], timeout=1200)
        else:
            _sh([ffmpeg, "-y", "-v", "error", "-i", str(raw),
                 "-vf", f"scale={VW}:{VH}:force_original_aspect_ratio="
                        f"increase,crop={VW}:{VH},fps=30",
                 "-t", "300", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                 "-preset", "veryfast", "-c:a", "aac", "-b:a", "128k",
                 str(norm)], timeout=3600)
        clips.append(norm)

    # 3. video track: concat clips, looped to cover the narration
    total_clip = sum(_probe_dur(ffprobe, c) for c in clips)
    reps = max(1, int(adur // total_clip) + 1)
    lst = work / "concat.txt"
    with open(lst, "w") as f:
        for _ in range(reps):
            for c in clips:
                f.write(f"file '{c}'\n")
    vtrack = work / "vtrack.mp4"
    _sh([ffmpeg, "-y", "-v", "error", "-f", "concat", "-safe", "0",
         "-i", str(lst), "-c", "copy", str(vtrack)], timeout=1200)

    # 4. subtitles (the builder's proportional allocator)
    srt = d / f"{item_id}.srt"
    _make_srt(manifest["script"], adur, srt)
    fsize = 30 if is_short else 24
    sub_style = (
        f"FontName=DejaVu Sans,FontSize={fsize},"
        f"PrimaryColour=&H00FFFFFF,OutlineColour=&H90000000,"
        f"BackColour=&H90000000,BorderStyle=1,Outline=2,Shadow=1,"
        f"MarginV={120 if is_short else 70},Alignment=2")

    # 5. assembly encode (single encode; bug + captions + title card)
    bug_fs = 30 if is_short else 26
    card_fs = 54 if is_short else 64
    vf = (f"drawtext=fontfile={font_b}:text='DAY FILE':"
          f"fontcolor={AMBER}:fontsize={bug_fs}:x=w-text_w-30:y=30:"
          f"box=1:boxcolor=0x000000@0.55:boxborderw=12,"
          f"subtitles={srt}:force_style='{sub_style}'")
    if manifest.get("title_card"):
        tc = _esc(manifest["title_card"])
        cy = 1500 if is_short else 880
        card_dur = 3 if is_short45 else 7
        vf += (f",drawtext=fontfile={font_b}:text='{tc}':"
               f"fontcolor=white:fontsize={card_fs}:x=(w-text_w)/2:y={cy}:"
               f"box=1:boxcolor=0x000000@0.6:boxborderw=20:"
               f"enable='lt(t,{card_dur})'")
    assembly = work / "assembly.mp4"
    _sh([ffmpeg, "-y", "-v", "error", "-i", str(vtrack), "-i", str(voice),
         "-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p",
         "-preset", "veryfast", "-c:a", "aac", "-b:a", "160k",
         "-t", f"{adur + 1.5:.2f}", "-shortest", str(assembly)],
        timeout=5400)

    # 6. loudnorm normalization pass (the press's long-master step):
    #    measure, then a linear loudnorm remux to I=-14 / TP=-1.0.
    final = d / f"{item_id}.mp4"
    loudnorm_mode = "skipped"
    if p.get("loudnorm", True):
        mi, mtp = _loudnorm_measure(ffmpeg, assembly)
        applied = False
        if mi is not None:
            ln = (f"loudnorm=I=-14:TP=-1.5:LRA=11:"
                  f"measured_I={mi}:measured_TP={mtp}:"
                  f"measured_LRA=11:measured_thresh=-25:"
                  f"offset=0:linear=true")
            r = subprocess.run(
                [ffmpeg, "-y", "-v", "error", "-i", str(assembly),
                 "-c:v", "copy", "-af", ln, "-c:a", "aac", "-b:a", "160k",
                 "-ar", "48000", str(final)],
                capture_output=True, text=True, timeout=3600)
            applied = r.returncode == 0 and final.exists()
            loudnorm_mode = "linear" if applied else "dynamic-fallback"
        if not applied:
            _sh([ffmpeg, "-y", "-v", "error", "-i", str(assembly),
                 "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
                 "-c:a", "aac", "-b:a", "160k", "-ar", "48000", str(final)],
                timeout=3600)
            loudnorm_mode = "dynamic" if mi is not None else \
                "single-pass-unmeasured"
    else:
        shutil.copyfile(assembly, final)

    # 7. thumbnail (builder's make_thumb: frame at 25% + PIL composite)
    from PIL import Image, ImageDraw, ImageFont, ImageEnhance
    import textwrap as _tw
    frame = work / "thumb_frame.jpg"
    _sh([ffmpeg, "-y", "-v", "error", "-ss", f"{adur * 0.25:.1f}",
         "-i", str(final), "-frames:v", "1", str(frame)])
    W2, H2 = 1280, 720
    if frame.exists():
        img = Image.open(frame).convert("RGB").resize((W2, H2),
                                                      Image.LANCZOS)
        img = ImageEnhance.Brightness(img).enhance(0.45)
    else:
        img = Image.new("RGB", (W2, H2), (10, 22, 51))
    dr = ImageDraw.Draw(img)
    fb = ImageFont.truetype(font_b, 40)
    dr.text((48, 36), "DAY FILE", font=fb, fill=(232, 163, 61))
    dr.line([(48, 92), (240, 92)], fill=(232, 163, 61), width=5)
    fbig = ImageFont.truetype(font_b, 92)
    y = 200
    for line in _tw.wrap(manifest.get("thumb_headline", ""), width=18)[:3]:
        dr.text((48, y), line, font=fbig, fill=(255, 255, 255),
                stroke_width=3, stroke_fill=(0, 0, 0))
        y += 112
    if manifest.get("thumb_sub"):
        fs = ImageFont.truetype(font_b, 44)
        dr.text((48, y + 20), manifest["thumb_sub"], font=fs,
                fill=(232, 163, 61), stroke_width=2, stroke_fill=(0, 0, 0))
    thumb = d / f"{item_id}-thumb.jpg"
    img.save(thumb, quality=90)

    # 8. measure + duration floor (longs: >= 480 s, builder has no floor;
    #    the floor is a job parameter and failing it is an item error)
    duration = _probe_dur(ffprobe, final)
    floor = p.get("min_duration_s")
    if floor and duration < float(floor):
        raise RuntimeError(
            f"duration floor: measured {duration:.1f}s < {floor}s")
    lufs, tp = _loudnorm_measure(ffmpeg, final)
    h = hashlib.sha256()
    with open(final, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    outputs = {
        "item_id": item_id, "format": fmt,
        "video_file": str(final.relative_to(wd)),
        "srt_file": str(srt.relative_to(wd)),
        "thumb_file": str(thumb.relative_to(wd)),
        "duration_s": round(duration, 2),
        "voice_duration_s": round(adur, 2),
        "loudness_lufs": lufs, "true_peak_db": tp,
        "loudnorm_mode": loudnorm_mode,
        "sha256": h.hexdigest(), "bytes": final.stat().st_size,
        "story_id": p.get("story_id"), "edition_id": p.get("edition_id"),
        "channel_job_id": p.get("channel_job_id"),
        "channel_id": p.get("channel_id"),
        "channel_name": p.get("channel_name"),
    }
    shutil.rmtree(work, ignore_errors=True)
    return outputs


HANDLERS = {"benchmark": job_benchmark, "image_convert": job_image_convert,
            "hash_manifest": job_hash_manifest, "text_pack": job_text_pack,
            "render": job_render}


def run_one(manifest, index, workdir):
    # P4 (per 82 reverify): the runner validates its manifest itself -
    # workflow-side validation alone doesn't count, and drain_local.py
    # calls run_one directly. A structural problem raises here (loud,
    # infrastructural) instead of surfacing as a fake per-item error.
    validate_manifest(manifest)
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


def write_result(result, out):
    # P7: atomic write - a killed runner never leaves a torn result.
    tmp = f"{out}.tmp"
    Path(tmp).write_text(json.dumps(result, indent=1))
    os.replace(tmp, out)
    print(json.dumps(result, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--index", type=int, default=None)
    ap.add_argument("--chunk", type=int, default=None,
                    help="P12: run every job in this chunk of a v2 "
                         "manifest, writing burst-result-<index>.json "
                         "per job (the workflow's chunked mode)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--workdir", default=".")
    args = ap.parse_args()
    if (args.index is None) == (args.chunk is None):
        print("INFRASTRUCTURE ERROR: pass exactly one of --index / "
              "--chunk", file=sys.stderr)
        return 2
    try:
        manifest = validate_manifest(
            json.loads(Path(args.manifest).read_text()))
        if args.chunk is not None:
            chunks = manifest.get("chunks")
            if chunks is None:
                raise ValueError("manifest has no chunks (v1) - "
                                 "use --index")
            if not 0 <= args.chunk < len(chunks):
                raise ValueError(
                    f"chunk {args.chunk} out of range "
                    f"0..{len(chunks) - 1}")
        elif not 0 <= args.index < len(manifest["jobs"]):
            raise ValueError(
                f"index {args.index} out of range "
                f"0..{len(manifest['jobs']) - 1}")
    except Exception as e:
        print(f"INFRASTRUCTURE ERROR: cannot load manifest/index: {e}",
              file=sys.stderr)
        return 2
    if args.chunk is not None:
        # Sequential in-chunk execution: per-job results keep the
        # exact v1 schema and filenames, so summary + ingest are
        # unchanged. A bad job errors in its own result, never the
        # chunk's (the failure model is per-JOB, never per-chunk).
        for ix in manifest["chunks"][args.chunk]["job_indices"]:
            result = run_one(manifest, ix, args.workdir)
            write_result(result, f"burst-result-{ix}.json")
        return 0
    result = run_one(manifest, args.index, args.workdir)
    write_result(result, args.out or f"burst-result-{args.index}.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
