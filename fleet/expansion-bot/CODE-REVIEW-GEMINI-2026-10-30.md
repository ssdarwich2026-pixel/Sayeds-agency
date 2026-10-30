# CODE REVIEW — GEMINI (verbatim capture)
**Asked:** Fri 2026-10-30, Pitch browser, Gemini (signed in), NEW thread: https://gemini.google.com/app/4167f45b64727b0b
**Prompt:** 82's workshopped prompt verbatim (`CODE-REVIEW-PROMPT-82-2026-10-30.txt`) + the full code packet inline (burst-batch.yml, tools/burst_runner.py, burst-benchmark.yml).
**Final decision (Section 9):** A — Keep the current architecture and patch it.

---

SECTION 1 — EXECUTIVE VERDICT

Is our current architecture fundamentally sound? No, it is a fragile, tightly coupled prototype rather than a robust production queueing system. It relies on GitHub Actions matrix limits, manual artifact merging, and lacks native backpressure, retries, or atomicity.

Is there a materially faster alternative? For pure throughput on free CPU lanes, no architectural alternative exceeds GitHub Actions' parallel runner fanout due to massive concurrency. However, for reliability, cost control, and GPU support, a cloud-native queue workers model (e.g., Temporal or Redis + container workers) is drastically superior.

What is your strongest recommendation? Retain GitHub Actions as the primary burst layer for free CPU execution, but decouple the state machine by introducing a proper persistent queue and explicit database/checkpoint tracking rather than relying on artifact globbing and client-side ingestion.

What is the biggest risk you found? Silent data corruption and false completion reporting. The summary workflow counts reported files, meaning if a runner fails to upload or write an artifact due to network drops or timeouts, the summary treats missing tasks as non-existent or fails to flag them correctly in upstream state reconciliation. Furthermore, shell injection vulnerabilities exist in burst_runner.py via unsanitized manifest fields passed to format strings.

SECTION 2 — ARCHITECTURE ALTERNATIVES
Architecture	Expected speed	Cost	Complexity	Main limitation	Verdict
GitHub Actions Matrix (Current)	~2,003 tpm	Free / Included	Low	256 matrix limit, runner spin-up latency, no real-time worker feedback	Retain for free CPU burst, but patch correctness
Self-Hosted Ephemeral Fleet	~2,500+ tpm	Variable (Cloud VMs)	High	Maintenance, scaling cold-starts, idle costs	Reject (Violates cost controls and adds undue infra overhead)
Cloud-Native Queue + Workers (AWS SQS/Lambda or Redis + Celery)	~1,800 tpm	Low/Moderate	Medium	Requires persistent broker infrastructure	Strongest Alternative for production scaling and GPU orchestration
Ray Distributed Framework	~2,100 tpm	High	High	Cluster management, networking complexity across cloud providers	Reject (Overkill and complex network setup)
Detailed Analysis of Strongest Alternative: Cloud-Native Queue + Workers (Redis/SQS + Container Worker Pool)

Exact technology and architecture name: Redis-backed worker pool with lightweight container/process workers.

How it would execute our specific workload: Tasks are pushed to a Redis queue. Ephemeral worker nodes (running on cheap cloud spot instances or local VMs, utilizing the free/guarded GPU lanes) pull tasks via reliable RPOP/BRPOPLPUSH, execute them locally, and update a central SQLite/PostgreSQL checkpoint state.

Expected throughput improvement and why: Comparable or slightly higher sustained throughput (~1,800–2,200 tasks/min) because it eliminates GitHub Actions' multi-minute queueing and container spin-up overhead per job batch.

Startup and scheduling overhead: Near-zero once workers are warm (sub-second task dispatch vs. 30–60 seconds for GitHub Actions runner provisioning).

Maximum practical concurrency and scaling constraints: Constrained only by Redis memory and worker availability, easily scaling past the 256-job GitHub Actions matrix limit.

Cost implications, including idle costs: Incurs idle costs if workers run continuously, but drops to near-zero if using serverless or auto-scaling container groups. Complies with the $250 operational ceiling if tied to strict spot-instance limits.

Operational complexity: Medium-High (requires managing broker state, worker monitoring, and log collection).

Failure recovery and retry behavior: Native transactional re-queuing (via BRPOPLPUSH or visibility timeouts) ensures zero silent job loss upon worker crashes—vastly superior to GHA artifacts.

Whether it preserves our ability to use free GPU lanes and one guarded paid GPU lane: Yes; workers can be explicitly targeted to specific hardware tags (e.g., gpu-free, gpu-paid).

Migration effort from our current implementation: Large (requires rewriting dispatchers and runner entrypoints).

Whether the improvement is substantial enough to justify replacing the current approach: No. For a team leveraging free GitHub Actions capacity under tight budget constraints, the migration cost and infrastructure overhead outweigh the benefits. Incremental patching of the GHA dispatcher is far more practical.

SECTION 3 — SOURCE-CODE AUDIT
ID	Severity	Classification	File	Line/function	Finding	Consequence	Concrete fix
AUDIT-01	CRITICAL	CONFIRMED	tools/burst_runner.py	job_text_pack (Line 139)	Unsanitized string formatting injection using template.format(**rec) and file_pattern.format().	Arbitrary attribute access or formatting errors if record payloads contain malicious template keys.	Validate/sanitize record keys or use safe string substitution.
AUDIT-02	HIGH	CONFIRMED	.github/workflows/burst-batch.yml	summary job (Line 79)	merge-multiple: true with wildcard download pattern burst-job-${{ inputs.batch_id }}-*.	If a runner fails silently or times out, missing artifacts cause glob sorting mismatches or incomplete tallying without failing the pipeline.	Explicitly check that len(results) == expected_count from the manifest.
AUDIT-03	MEDIUM	CONFIRMED	tools/burst_runner.py	job_benchmark (Line 42)	Hardcoded 900-second timeout on subprocess run without incremental output monitoring.	Process hangs or infinite loops lock up the runner for up to 15 minutes with no telemetry.	Implement asynchronous stream reading with heartbeat timeouts.
AUDIT-04	MEDIUM	CONDITIONAL	tools/burst_runner.py	job_hash_manifest (Line 85)	glob.glob with recursive=True across broad workspace paths.	Can lead to high memory consumption or unintended file scanning if patterns are overly broad.	Enforce strict path boundaries under workdir.
SECTION 4 — SILENT DATA LOSS AND FAILURE ANALYSIS

Manifest creation: The batch manifest (batches/<batch-id>.json) is packed locally. If jobs are omitted or duplicated during packing, downstream systems have no way of knowing original intent.

Dispatch: A human triggers workflow_dispatch. If inputs are mistyped, the setup job fails early.

Runner acquisition: GitHub Actions queues matrix shards. If concurrency limits are hit, jobs sit indefinitely in queued status without throwing explicit errors.

Execution: burst_runner.py executes the task. If a task crashes with an unhandled Python exception, run_one catches it and writes status: "error", exiting with code 0. Risk: The workflow step succeeds even when the underlying task fails.

Result production: Result JSON is written locally. If disk space is exhausted or permissions fail, no result file is created.

Persistence: actions/upload-artifact@v4 uploads the result. If network drops occur during upload, the artifact is lost.

Aggregation: The summary job downloads artifacts via merge-multiple: true. If an artifact failed to upload, it is silently absent from glob.glob("burst-result-*.json"). Data Loss Point: The summary job totals only the files it successfully finds, treating missing jobs as non-existent rather than failed.

Final completion reporting: ingest_results.py (external) reads the summary. Because the summary undercounted missing jobs, the central checkpoint closes jobs incorrectly or leaves them hanging.

SECTION 5 — TOP FIVE IMPROVEMENTS

Explicit Manifest Count Validation in Summary

Expected benefit: Prevents silent job loss by failing the workflow if reported result counts do not match manifest lengths.

Implementation effort: SMALL

Regression risk: Low

Improves: Reliability

Priority: Implement immediately.

Sanitize Template Inputs in job_text_pack

Expected benefit: Prevents formatting injection bugs and runtime crashes.

Implementation effort: SMALL

Regression risk: Low

Improves: Correctness

Priority: Implement immediately.

Strict Non-Zero Exit on Critical Runner Failures

Expected benefit: Ensures GitHub Actions correctly marks workflows as failed when infrastructure or critical execution steps break.

Implementation effort: SMALL

Regression risk: Low

Improves: Reliability

Priority: Immediate.

Artifact Checksum Verification

Expected benefit: Validates result integrity before aggregation.

Implementation effort: MEDIUM

Regression risk: Low

Improves: Reliability

Priority: Deferred.

Dynamic Matrix Sharding Chunking Optimization

Expected benefit: Improves load balancing across large batches.

Implementation effort: MEDIUM

Regression risk: Medium

Improves: Speed

Priority: Deferred.

SECTION 6 — BENCHMARK VERDICT

Is the 6.86x comparison valid? Partially valid / Misleading. The benchmark compares a localized single-VM sequential/multithreaded loop (burst-benchmark.py) against an elastic, massively parallel distributed cloud runner pool (GitHub Actions matrix). While the math (tasks_per_min) for the specific workload is correct while running, it ignores runner provisioning latency, queue wait times, and artifact transfer overhead.

Improved benchmark protocol:

End-to-End Latency: Measure time from workflow_dispatch trigger to final summary artifact availability.

Effective Throughput: Successful Unique Tasks / Total Wall-Clock Minutes (including queue time).

Reliability Rate: (Successful Tasks / Total Dispatched Tasks) * 100.

SECTION 7 — MINIMUM PATCH PLAN

File: .github/workflows/burst-batch.yml (summary job)

Function: Python inline summary block.

Change: Add explicit length check: if len(results) != expected_count: raise SystemExit("Mismatch between manifest and reported results!").

File: tools/burst_runner.py

Function: job_text_pack

Change: Validate record keys against template fields to prevent injection or key errors.

SECTION 8 — CLAIMS REQUIRING VERIFICATION

Actual GitHub Actions queue wait times during peak hours in the sayeds-agency repository.

Complete execution logs and artifact payloads from a live 256-job matrix run.

Verification of local VM baseline hardware specifications (CPU/RAM constraints during the 292 tpm run).

SECTION 9 — FINAL DECISION

A. Keep the current architecture and patch it.

Explanation: The current GitHub Actions burst-batch design successfully achieves high parallel throughput utilizing free tier capacity while strictly adhering to financial constraints ($0 out-of-pocket, zero risk of exceeding promotional or internal cost ceilings). Replacing it is unjustifiable given the migration cost; instead, patching the silent failure gaps in artifact aggregation and input sanitization secures the pipeline.
