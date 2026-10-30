# P12 DESIGN — Chunked Sharding + In-Runner Pool (2026-10-30)

_Status: **BUILT 2026-10-30** (design below as written pre-build).
Manifest v2 chunks in pack_batch.py (--chunk-size 8 default, --no-chunk
for v1), validator chunk rules in burst_runner.py, --chunk range mode,
workflow matrix over legs (v1 manifests still run per-job), drain
--tiny-only pool (#14) with ingest-identical judging incl. content
verification. Proof: regression 24/24, integration gate PASS on both
the v1 and chunked pipelines, sync 6/6. LIVE measurement (wall-clock
vs Batch-#3 shape) still owed — it lands with the first real chunked
batch; no speedup number is quoted until then._

## Problem (measured, not theorized)
Every matrix leg pays fixed overhead: checkout + setup-python + pip
install (when needed) + runner spin-up ≈ tens of seconds, regardless
of job size. For tiny jobs (hash manifests, small text packs, format
converts of small art), overhead dominates: Batch #2/#3 ran 35–42s
wall for 4 jobs whose actual work was seconds. One-job-per-leg also
burns the 256-matrix ceiling 1:1 and multiplies artifact uploads.

## Design
1. **Chunking at pack time** (`pack_batch.py`): consecutive pending
   jobs are grouped into chunks of up to K jobs (default K=8) or a
   chunk byte/time budget, whichever hits first. Jobs flagged
   `"heavy": true` (benchmarks, large converts) always get a solo
   chunk — heavy-job throughput is unchanged by design.
2. **Manifest v2**: batch manifest gains `chunks: [{chunk_id, job_ids}]`
   alongside `jobs` (backwards-compatible: a v1 manifest = every job
   its own chunk). The validator learns the chunk rules (IDs unique,
   every job in exactly one chunk, chunk count ≤ 256).
3. **Workflow matrix over chunks**, not jobs: setup emits chunk
   indices; each leg runs the runner in range mode.
4. **Range mode in burst_runner.py**: `--chunk N` executes the chunk's
   jobs sequentially in-process (they're tiny; sequential is honest
   and keeps per-job result files identical). An in-runner process
   pool (2–4 workers) is a v2.1 option ONLY if sequential chunk runs
   measure slow — do not build the pool on spec.
5. **Results unchanged**: one `burst-result-<global-index>.json` per
   job, same schema, uploaded as one artifact per chunk
   (`burst-chunk-<batch>-<chunk>`); the summary reconciliation (P2)
   keys off global indices and expected count exactly as today.
   ingest_results.py does not change at all — the checkpoint contract
   is the invariant this design exists to protect.
6. **VM drain for tiny tasks**: drain_local.py gains a `--tiny-only`
   pass that drains sub-second job types (hash_manifest, text_pack)
   locally in a process pool before anything is packed for Actions —
   the seam already exists (drain imports burst_runner.run_one).

## Expected effect (to be MEASURED, not claimed)
- Small-job batches: wall-clock per batch drops toward the slowest
  chunk instead of the sum of per-leg overheads; runner minutes per
  batch fall roughly by the chunk factor on overhead-bound work.
- Heavy jobs: no change (solo chunks). GPU work: unaffected (Actions
  has no GPU — unchanged truth).
- Measurement plan: re-run a Batch-#3-shaped manifest (4 jobs: 2 hash,
  1 text, 1 bench) pre/post P12; report wall-clock, runner minutes,
  and per-job results identical (hash-compare outputs). Only then
  does any speedup number get quoted.

## Risks / guards
- One bad chunk-mate must not poison siblings: range mode catches
  per-job exceptions into per-job error results exactly as run_one
  does today (the failure model is per-JOB, never per-chunk).
- Artifact granularity coarsens (per chunk): a dead leg loses its
  whole chunk's results — reconciliation (P2) + ingest (stays
  packed, never guessed) already handle missing indices honestly;
  chunks stay small (K≤8) to bound the blast radius.
- Fair use unchanged: chunking REDUCES runner usage; the no-timer,
  real-work-only rule is untouched.

## Build order
1. Validator + manifest v2 in burst_runner.py (+ fleet copy sync).
2. pack_batch.py chunking (with `--chunk-size`, default 8, `--no-chunk` escape).
3. Workflow: matrix over chunks + range-mode call; summary unchanged.
4. drain_local.py --tiny-only pool pass.
5. Measurement batch (real jobs, Batch-#3 shape) + report; then the
   design closes or iterates. Single-source the two burst_runner.py
   copies as part of this build (symlink or copy-on-commit check) so
   P1–P11-style dual patching never recurs.
