# 82 REVERIFY — adjudication of the burst-dispatcher reviews (verbatim)
**Chat:** https://chatgpt.com/c/6ae4c270-0a3c-83ee-b636-604047bd439e ("Review adjudication and patches"), Fri 2026-10-30, ran 10:53–11:16 CDT.
**Input:** 81's full adjudication pasted verbatim + 4 closing questions. **Outcome:** 82 co-signs the adjudication + Architecture A, refines the order, adds the integration regression gate.

---

81 — Final adjudication and patch approval

My overall ruling: I co-sign your adjudication and the A architecture decision, with a few refinements to the implementation order.

Your most important correction is the distinction between a workflow artifact reporting success and the underlying checkpoint system actually losing work.

That distinction matters. The reviewers identified a genuine observability and workflow-completion defect, but the dispatcher-side evidence changes its severity. The checkpoint model remains sound based on the source you examined.

I would not replace the architecture. I would make the existing architecture harder to break, easier to audit, and faster at small-task execution.

One qualification: I'm evaluating the source-level findings and evidence presented in your adjudication, not independently claiming to have rerun or inspected the repository. I won't pretend to have verified code I haven't received.

1. Do I dispute any verdict or severity?

I have no major disagreement. I would refine five items.

- P2 — Summary reconciliation | Agree: MEDIUM | The checkpoint protects system correctness; the artifact still misrepresents completeness.
- P4 — Manifest validation | Agree, raise priority | Invalid manifests can escape the normal per-job failure reporting path.
- P6 — Shell interpolation | Agree: LOW–MEDIUM | Owner-controlled inputs reduce exploitability, not the need for safe handling.
- P9 — Path containment | Agree, strengthen | Preventing traversal must happen before any filesystem operation, not after writing.
- P10 — Benchmark accuracy | Agree, raise priority for performance decisions | A misleading throughput figure can cause us to optimize the wrong architecture.

Two additional observations:

P2: Don't equate errors with incomplete work. A batch can be completely accounted for and still contain failed jobs. Distinguish: complete (every expected job has a terminal, evidenced result), successful (every expected job succeeded), failed (number of terminal failures), missing (expected jobs without a result). A batch with 100 accounted-for jobs and 3 failures is complete but unsuccessful; 97 results + 3 missing is incomplete. The workflow should fail when either condition violates the required success policy.

P4: Validate before execution, not just at dispatch. The runner must independently validate its manifest; a workflow-only validator is insufficient because the runner is also an executable interface invoked separately.

P9: Containment must precede writes. Resolve and validate the destination before creating directories, writing files, or converting images. Checking containment after a write is too late.

P10: Keep two different throughput metrics. Label the aggregate active-execution metric correctly and add end-to-end wall-clock throughput.

P12: Don't assume chunking is automatically faster. It reduces setup overhead but increases failure-domain size; preserve per-job receipts and retries inside chunks.

P3: One subtle workflow dependency issue. When implementing P2, make sure the summary job runs even when the execution job fails — use if: always(), inspect dependency results, still produce a failure summary. Otherwise the very failures we're trying to report can prevent the reporting job from running.

2. Is the patch order right?

Mostly. One important change: shared validation + regression tests before multiple workflow changes. Preferred order: P1 JPEG → P4 manifest validation → P5 filename collision → P9 path containment → P7 atomic writes → P8 hash-manifest → P6 safe inputs → P2 summary reconciliation → P3 artifact enforcement → P11 pinning/conditional Pillow/concurrency/retention → P10 benchmark integrity → P12 chunking + VM drain. First seven establish input/execution/filesystem correctness; P2/P3 then make the workflow report those outcomes reliably. P11 change: concurrency group keyed by batch ID with cancel-in-progress: false.

3. Did all four of us miss anything material? Six areas (design recommendations, not confirmed defects):

A. Artifact-to-checkpoint identity — every result should carry batch_id, job_id, manifest hash/version, attempt number, runner/shard identity, status, result schema version; ingest rejects mismatched identities and stale attempts. Matters most once chunking lands: a valid JSON result is not necessarily a valid receipt for the current job.
B. Retry and duplicate-execution semantics — explicit tests: same result ingested twice; old attempt after newer; two workers on one job; runner dies after result but before upload; upload succeeds while ingest fails. Goal: exactly-once ACCOUNTING, not exactly-once execution.
C. Symlink-based path escapes — P9 must cover symlinks, not just .. and absolute paths; resolved paths, trusted output root.
D. Supply-chain reproducibility — Actions pinned to full commit SHAs, deps locked/hash-verified, explicit Python version, no floating versions.
E. Chunk scheduling and straggler control — small bounded chunks, configurable pool workers, individual job timeouts, individual receipts, independent retries, no loss of completed jobs when a chunk-mate fails; a chunk is NOT one indivisible transaction.
F. Regression tests across the dispatcher boundary — 82's strongest addition: an integration test manifest → pack_batch → burst_runner → result artifact → ingest_results → burst_state, success + deliberate failures, proving: every expected job accounted for; missing stays missing; failed attempts recorded; duplicate receipts don't double-close; partial chunk safely retryable; summary agrees with checkpoint. This becomes the regression gate for every future architecture change.

4. Final patch plan I co-sign — Architecture A approved. Final sequence (order | patch | acceptance):
1 JPEG normalization — JPEG/JPG/PNG/WEBP tests pass
2 Manifest validator — invalid schema, IDs, bounds, indices rejected
3 Filename collision protection — duplicate names and pack.txt rejected
4 Path containment — no write outside approved roots, including symlink cases
5 Atomic result writes — interrupted writes cannot leave partial JSON receipts
6 Hash-manifest validation — empty file matches cannot silently succeed
7 Safe workflow inputs — env-based inputs, validated batch IDs
8 Summary reconciliation — expected/completed/failed/missing counts accurate
9 Artifact enforcement — missing expected artifacts explicitly fail
10 Runtime reproducibility — deps pinned, conditional Pillow, concurrency, retention
11 Benchmark correction — four-shard reconciliation + wall-clock throughput
12 Integration regression gate — dispatcher-to-checkpoint tests pass
13 Chunked sharding — bounded chunks, process pools, independent receipts/retries
14 VM process-pool drain — tiny jobs use the local seam where benchmarks justify it

Three mandatory rules: (1) every patch lands in both source locations with automated byte-equivalence/sync checks; (2) every correctness patch includes a regression test before merging; (3) no P12 rollout until the original architecture passes the correctness suite.

Decision: KEEP existing architecture; PATCH correctness/observability first; OPTIMIZE via chunked execution second; DEFER the persistent lease-based worker pool (reconsider only if chunked execution measurably leaves performance on the table). Strategic: three benchmark categories before P12 (tiny/medium/heavy) with identical workloads old-vs-new. Bottom line: the external reviews validated the workflow's weaknesses; the dispatcher investigation prevented misdiagnosing the checkpoint architecture — independent reviews must be followed by source-level adjudication. P1–P11 authorized as the hardening program with the integration gate added; P12 is the next milestone, not a redesign excuse.
