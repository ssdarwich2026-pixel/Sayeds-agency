# CODE REVIEW — PERPLEXITY (verbatim capture)
**Asked:** Fri 2026-10-30, Pitch browser, Perplexity (guest session, no signup), NEW thread: https://www.perplexity.ai/search/002c593c-19ea-455c-915a-cb09f4a2f302
**Prompt:** 82's workshopped prompt verbatim (`CODE-REVIEW-PROMPT-82-2026-10-30.txt`) + the full code packet inline (burst-batch.yml, tools/burst_runner.py, burst-benchmark.yml). Composer accepted the full 26,550 chars.
**Final decision (Section 9):** A — Keep the current architecture and patch it.

---

SECTION 1 — EXECUTIVE VERDICT

Your architecture is reasonable for bounded, human-dispatched CPU batches, but its completion protocol is not yet reliable enough to establish that every requested job finished correctly. It also does not implement GPU orches orchestration: all execution targets are ubuntu-latest.

No supplied evidence establishes a materially faster replacement. The strongest alternative to test is a persistent, lease-based worker pool on existing approved resources, with GitHub Actions retained for burst capacity. It could eliminate per-item runner provisioning, checkout, dependency installation, and artifact overhead; the improvement remains an unmeasured hypothesis.

My strongest recommendation is A: keep and patch before considering replacement. First establish exact completion accounting and output integrity, then benchmark bounded multi-job shards against the existing one-job-per-runner design and a warm worker-pool prototype.

The biggest confirmed risk is false-green completion: run_one() converts item failures into JSON while exiting zero, and the summary neither fails on those errors nor reconciles results against the expected manifest. Separate confirmed defects can overwrite text outputs and silently omit hidden output files from artifacts.

I read all three supplied files in full. I did not execute tests or access your repository. The benchmark implementation, queue packer, result ingester, baseline data, and live run records were not supplied.

SECTION 2 — ARCHITECTURE ALTERNATIVES

The crucial distinction is between accelerating the synthetic benchmark and reducing time to durable, validated completion of your actual work. The supplied implementation demonstrates neither their equivalence nor that scheduling is the dominant bottleneck.

Comparison

“Expected speed” below describes mechanisms and hypotheses, not measured speedups.

Architecture	Expected speed	Cost	Complexity	Main limitation	Verdict
Current GitHub Actions dynamic matrix; one item per runner	Supplied approximately 2,003 tasks/min concerns the reported benchmark, not established production-item throughput	Depends on repository visibility, plan, included usage, and billing configuration	Low–medium	Per-item checkout/setup/upload; incomplete reconciliation	Retain provisionally; patch
Bounded multi-item shards within the existing matrix	Likely lower overhead for short items; magnitude unmeasured	No new infrastructure; potentially fewer setup operations	Medium	Larger shards increase straggler and retry exposure	First performance experiment
Reusable workflows / workflow_call fanout	No established speed advantage by itself	Same underlying runner consumption	Medium	Refactoring orchestration does not remove execution overhead	Use for maintainability, not as a throughput claim
Persistent lease-based worker pool on existing approved machines	Potentially materially faster end-to-end for short, frequent tasks	Zero incremental infrastructure cost only if existing free/approved capacity and storage suffice	Medium–high	Requires durable leases, fencing, result persistence, and reconciliation	Strongest complementary candidate
Ephemeral self-hosted runners using Actions Runner Controller	Depends on provisioning and available hardware; cold provisioning still exists	Cluster, compute, storage, and idle capacity require explicit costing	High	No supplied Kubernetes fleet or approved capacity	Not justified now
Container workers on an existing host	Could amortize environment setup; no inherent additional compute	Existing-host costs; image storage and transfer must fit existing allowances	Medium	Containers alone do not provide durable scheduling	Useful packaging for a worker pool
Ray Core task pool on existing approved machines	Unmeasured; useful only if task granularity, data movement, and available resources justify it	Existing resources only for a zero-new-spend trial	High relative to this runner	Task overhead; external result durability still required	Defer pending workload evidence
AWS Batch / Google Cloud Batch / OCI Container Instances with an external queue	Unestablished; provisioning may dominate small tasks	Paid infrastructure and ancillary charges; no approved unit-cost model supplied	High	No demonstrated benefit or approved financial envelope	Do not deploy under present evidence

GitHub documents a 256-job matrix limit; actual simultaneous execution is a separate account/plan constraint. Its published standard-runner limits include 20 concurrent jobs for Free, but your effective available capacity must be verified rather than inferred from comments.
docs.github

Ray explicitly warns that very small tasks may not benefit: its documentation says speedups are unlikely for tasks taking less than ten milliseconds and recommends batching. That is a warning against assuming a distributed framework automatically improves small-job throughput.
docs.ray

Strongest alternative: persistent lease-based worker pool

Exact proposed architecture: an application-level SQLite-WAL lease queue on the existing dispatcher VM, exposed through an authenticated dispatcher service, with Python ProcessPoolExecutor workers on existing approved CPU machines. Remote workers use the service rather than mounting the SQLite database. GPU workers would be separate capability-labelled consumers.

This is a proposed architecture, not an existing component established by the packet.

How it would execute this workload

Freeze a manifest and assign each logical item an identity containing batch ID, index, manifest digest, and handler/environment version.

Dispatchers transactionally lease ready items.

Warm workers call the existing handlers through a small execution adapter.

Each attempt writes into a distinct staging directory.

Workers persist outputs and a checksum inventory to approved durable storage.

The dispatcher accepts completion only after validating identity, inventory, and the current lease token.

Expired leases become eligible for bounded retry. A stale worker cannot commit over a newer lease.

GitHub Actions remains an optional burst executor using the same item/result contract.

Expected improvement and overhead

No numerical speedup is defensible yet.

For 
𝑁
N short items, concurrency 
𝐶
C, execution time 
𝑡
t, and per-item orchestration overhead 
ℎ
h, a simplified estimate is:

𝑇
c
u
r
r
e
n
t
≈
𝑇
s
e
t
u
p
+
⌈
𝑁
/
𝐶
⌉
(
𝑡
+
ℎ
)
+
𝑇
a
g
g
r
e
g
a
t
i
o
n
.
T
current
	​

≈T
setup
	​

+⌈N/C⌉(t+h)+T
aggregation
	​

.

Warm workers could reduce 
ℎ
h, but they do not create CPU capacity. A smaller existing fleet can lose to GitHub's larger available fleet even after removing most scheduling overhead.

Measure these competing effects. Do not substitute a theoretical scheduling advantage for a demonstrated application speedup.

Concurrency, cost, recovery, and migration
Requirement	Assessment
Startup/scheduling	Warm workers avoid a fresh runner environment per item. Actual polling/lease latency and cold worker startup remain unmeasured.
Practical concurrency	Limited by actual approved CPU/GPU capacity, memory, storage bandwidth, dispatcher capacity, and workload resource requirements—not an invented fleet size.
Idle cost	No incremental compute bill only if existing machines would already remain running. Otherwise idle time has a cost and needs approval.
Recovery	At-least-once execution with lease expiry; exactly-once acceptance requires fenced commits and idempotent result ingestion.
Free GPU lanes	Preserved in principle through capability-labelled workers, subject to each provider's availability, networking, and automation rules. None are established by these files.
Guarded paid GPU lane	Disabled by default; consume only an already-approved allocation or require explicit owner approval before launch.
Migration	MEDIUM for a prototype; LARGE for production-grade remote persistence, leases, authentication, fencing, and operations. Existing handlers can be reused after path and output fixes.
Replacement justified?	No. First test whether overhead dominates and whether existing resources offer adequate parallel capacity.

Ray does supply worker-failure retry mechanisms, but application exceptions are not retried by default; retry settings must be explicit. In this implementation, run_one() returns errors as ordinary values, so wrapping it in a Ray task would not automatically make those item errors retryable.
docs.ray

Financial restrictions

No recommendation here authorizes a new paid resource.

Any eventual paid-lane design must satisfy all of the following:

Owner approval before each additional paid-resource launch.

Internal stop at $250 consumed; $50 reserve is not available execution budget.

An independently enforced maximum exposure within the $300 credit ceiling.

No reliance on promotional-credit renewal.

No wallet signatures, transactions, or out-of-pocket spending.

Conservative accounting for reporting delay, in-flight jobs, storage, networking, and teardown.

The packet contains no billing controller or evidence that a $250 stop exists. Therefore paid execution remains unverified, not approved. A delayed billing reading alone cannot establish that accrued charges remain below the ceiling.

SECTION 3 — SOURCE-CODE AUDIT

Locations below use exact functions or workflow steps, as permitted by the request. “CONFIRMED” establishes code behavior, not that a production incident has occurred. “CONDITIONAL” identifies a concrete trigger not proven to exist in your manifests.

Findings
ID	Severity	Classification	File	Line/function	Finding	Consequence	Concrete fix
BB-01	HIGH	CONFIRMED	tools/burst_runner.py; .github/workflows/burst-batch.yml	run_one(), main(); “Build batch summary from result read-backs”	Handler exceptions become status: error; main() returns 0; summary counts errors but never rejects them.	All items can fail while every workflow job succeeds.	Preserve error artifacts, but make final batch acceptance fail when any expected item is unsuccessful.
BB-02	HIGH	CONFIRMED	.github/workflows/burst-batch.yml	Summary job	jobs_reported = len(results) is never compared against setup.count or the manifest; IDs, indices, batch identity, and uniqueness are not checked.	Summary may describe an incomplete set without reporting missing work. Infrastructure failures may make the overall workflow red, but the summary is still not proof of completeness.	Pass manifest identity/count to summary; reconcile the exact expected item set and reject missing, duplicate, unexpected, or mismatched results.
BB-03	HIGH	CONDITIONAL	Both workflow files	Setup Python; batch execution shell; batch summary Python; benchmark execution shell	Raw ${{ inputs.batch_id }} and ${{ inputs.iterations }} enter executable script text. Quoting does not make arbitrary interpolated text safe.	A malicious dispatch input can execute code with that job's available workspace/token access. No supplied evidence establishes access to additional secrets.	Pass inputs through environment variables; validate batch IDs and parse bounded integers before use.
BB-04	HIGH	CONDITIONAL	tools/burst_runner.py	out_dir(), job_image_convert(), job_text_pack(), job_hash_manifest()	Job IDs, output names, file patterns, and input paths lack root-containment checks. Absolute paths, .., and symlink escapes are not rejected.	Writes or reads can escape intended roots; an error after a write does not undo it.	Validate IDs and resolve all paths against explicit allowed roots; reject escapes and unsafe symlinks before I/O.
BB-05	HIGH	CONFIRMED	tools/burst_runner.py	job_text_pack()	Generated filenames are not checked for uniqueness or collision with reserved pack.txt.	Multiple records can overwrite one another and still return status: ok; files can list the same output repeatedly.	Precompute and validate all names, reject duplicates and pack.txt, then write.
BB-06	HIGH	CONDITIONAL	.github/workflows/burst-batch.yml; tools/burst_runner.py	Manifest setup; out_dir(); summary artifact download	Duplicate job IDs share the same output namespace. Summary uses merge-multiple: true.	Distinct shard outputs with identical relative paths overwrite during download; both item results can remain ok.	Reject duplicate IDs and preserve separate artifact directories until validation; preferably namespace outputs by item identity.
BB-07	HIGH	CONDITIONAL	.github/workflows/burst-batch.yml	Run-job upload step	burst_out/ is uploaded without an explicit hidden-output policy. Handlers permit hidden filenames and hidden job directories.	A job can report ok while its declared hidden outputs never enter the artifact.	Reject hidden output paths, or upload only a validated explicit inventory with hidden files deliberately enabled.
BB-08	MEDIUM	CONFIRMED	tools/burst_runner.py	job_image_convert()	ext accepts "jpeg", and conversion checks accept it, but the im.save() format map has no "jpeg" key.	Every format: jpeg job reaches a KeyError instead of saving successfully.	Normalize jpeg to jpg once, or include "jpeg": "JPEG" in the save map.
BB-09	MEDIUM	CONDITIONAL	tools/burst_runner.py	job_hash_manifest()	A pattern is considered present if glob() returns anything, even when only directories matched and no file was processed.	With require_all: true, a directory-only pattern can produce an empty successful manifest.	Define file-match semantics; require at least one eligible file per required pattern, or explicitly support recursive directory expansion.
BB-10	MEDIUM	CONDITIONAL	tools/burst_runner.py	Output-producing handlers; main()	Output and result writes are direct, with no staging/commit boundary. Failed handlers can leave earlier files behind; upload runs with always().	Partial attempt outputs can be published. Reused local workdirs can retain stale files across retries.	Use per-attempt staging; publish a validated inventory only after success; atomically replace the final result JSON.
BB-11	MEDIUM	CONFIRMED	.github/workflows/burst-batch.yml; tools/burst_runner.py	Setup; main(), run_one()	No complete manifest validation: missing IDs/types fail before item error handling; duplicate IDs are accepted; negative CLI indices select from the end. The workflow does not enforce its declared matrix-size bound.	Malformed input becomes inconsistent infrastructure failures or unintended selection instead of a clean preflight rejection.	Centralize schema validation, unique-ID checks, explicit 0 <= index < count, and batch-size policy before fanout.
BB-12	MEDIUM	CONDITIONAL	tools/burst_runner.py	job_hash_manifest(), job_text_pack(), job_image_convert()	read_bytes() loads whole files; text output accumulates in memory; dimensions, records, glob scope, and output bytes are unbounded.	A large or erroneous manifest can exhaust memory, disk, or job time.	Stream hashing; enforce per-type size/count/dimension/output limits; bound local execution time.
BB-13	MEDIUM	CONFIRMED	.github/workflows/burst-benchmark.yml	“Total the shards”	Adds rates from whichever matching result files exist; does not verify four shard identities, successful operation counts, common wall time, or output correctness.	The number is not a verified end-to-end batch rate and cannot establish production dispatcher throughput.	Reconcile shard IDs/counts and calculate durable unique completions over a shared measured interval.
BB-14	MEDIUM	CONFIRMED	.github/workflows/burst-batch.yml	“Install Pillow”; action references	Unpinned Pillow is installed for every item; action major tags and ubuntu-latest are mutable.	Environment reproducibility is incomplete; all item types incur the Pillow installation step.	Lock application dependencies and approved action revisions; install Pillow only where required; record runtime versions.

The external behaviors behind BB-06 and BB-07 are documented: merged artifacts use last-writer-wins for colliding filenames, and upload-artifact@v4 excludes hidden files by default. Its default missing-file behavior is a warning, not failure.
github
+1

Trigger and verification tests

These are proposed tests, not executed results.

ID	Realistic trigger / verification test
BB-01	Submit a valid image job pointing to a nonexistent input. Verify that the current item produces an error JSON and that patched batch acceptance fails while preserving diagnostics.
BB-02	Run a three-item fixture; remove one result before aggregation. Also supply a duplicate index and wrong batch ID. Each must produce explicit reconciliation failure.
BB-03	In an isolated test repository, use quote-breaking inputs containing only a harmless marker operation. After patching, inputs must be rejected or treated exclusively as data.
BB-04	Test ../escape, absolute paths, and an in-root symlink pointing outside the root for every input/output path parameter. No external write/read should occur.
BB-05	Use two records with file_pattern: same.txt, then one record with file_pattern: pack.txt. Both manifests must be rejected before writing.
BB-06	Give two text jobs the same ID and different contents for item-00.txt. Preflight must reject them; aggregation must independently reject namespace collisions.
BB-07	Generate .hidden.txt and use a hidden job directory. Verify the chosen policy: preflight rejection, or verified artifact round-trip with matching checksums.
BB-08	Convert a small PNG using each accepted format, explicitly including jpeg.
BB-09	Set paths to an existing empty directory with require_all: true; test missing paths and explicit recursive globs separately.
BB-10	Terminate a writer mid-output; also fail formatting on the second record. No successful commit or accepted partial output should remain. Repeat using a reused local workdir.
BB-11	Test missing keys, wrong types, duplicate IDs, an empty batch, oversized batches, and CLI indices -1 and len(jobs).
BB-12	Exercise declared file-size, record-count, dimension, and total-output limits. Verify bounded rejection rather than runner termination.
BB-13	Supply only three shard results; supply duplicate shard identities; stagger shard start times. Aggregation must reject invalid sets and distinguish end-to-end from active execution rates.
BB-14	Rebuild from the same commit and lock data twice; compare recorded dependencies/environment and outputs. Confirm non-image shards do not install Pillow.
Important limits on these findings

BB-03 is not evidence of an unauthenticated public exploit; workflow-dispatch access and repository controls determine exposure.

BB-04 is not evidence that supplied manifests are malicious.

No code proves that ingest_results.py incorrectly closes jobs; that file is absent.

No bespoke GitHub API polling loop is supplied, so an actual API-rate-limit defect cannot be established.

No paid resource launcher is supplied, so paid overspending cannot be attributed to these files.

The benchmark script is absent; its internal correctness cannot be audited from workflow comments.

SECTION 4 — SILENT DATA LOSS AND FAILURE ANALYSIS

The lifecycle below separates observable implementation from missing components.

Stage	What the packet establishes	Loss, duplication, or false-success exposure	Required safeguard
Manifest creation	Comments say pack_batch.py commits a manifest.	Packer, queue claiming, duplicate IDs, immutable identity, and transactional behavior are unverified.	Inspect packer; validate and digest an immutable manifest.
Dispatch	Human supplies batch_id.	Repeated dispatch can repeat execution; no cross-run deduplication is shown. Raw input interpolation is unsafe under BB-03's condition.	Safe input handling; logical batch/item identities; explicit replay policy.
Setup	Reads manifest and emits indices.	Only matching batch_id is checked. Invalid item structure and duplicate IDs survive preflight.	Full validation before creating matrix jobs.
Runner acquisition	Each index gets an independent hosted runner job.	Queuing, cancellation, unavailable capacity, or runner failure may prevent execution. No result exists yet.	Track expected items independently of acquired runners.
Execution	main() calls one handler.	Handler failure becomes zero-exit error JSON. Local retries can reuse stale directories. Resource exhaustion can prevent any result.	Explicit item states, limits, attempt isolation, and bounded retries.
Result production	Handlers write files; main() writes JSON afterward.	Name collisions can destroy outputs while returning ok; abrupt termination can interrupt writes.	Prevalidated names, staging, checksummed inventory, atomic result publication.
Persistence	Run-job upload executes under always().	Hidden outputs may be omitted; failed attempts can upload partial files; abrupt termination cannot guarantee upload.	Verify declared files actually exist in persisted artifacts; classify missing persistence as unresolved.
Aggregation	Downloads matching artifacts and parses result JSON files.	No expected-set reconciliation; merged output collisions; no file-checksum validation. Malformed JSON can abort aggregation rather than produce a structured incomplete report.	Separate download directories; validate identity, schema, completeness, and inventory.
Workflow completion	Summary reports counts but does not fail on item errors.	All-item failure can still yield a green workflow. A green summary is not an acceptance certificate.	Explicit final batch outcome derived from reconciled state.
Dispatcher ingestion	Comments assign checkpoint closure to ingest_results.py.	Actual deduplication, artifact retrieval, retention handling, retries, and checkpoint commits are unknown.	Audit ingester and verify idempotent acceptance plus recovery from interrupted ingestion.
Cancellation and timeout

The workflow's timeout-minutes: 30 bounds each production shard, not each handler's logical transaction. Only job_benchmark() has an explicit subprocess timeout. No supplied code implements graceful checkpointing or an external watchdog for direct local handler calls.

if: always() is useful for ordinary step failures, but it is not a durability protocol for a terminated runner. Reconciliation must classify any expected item without a validated result as unresolved, regardless of workflow status.

Exactly-once expectations

The defensible target is:

Execution may repeat.

Every attempt has a distinct identity.

Only one verified result is accepted for each logical item.

No missing or ambiguous item is silently closed.

Neither cross-run leases nor idempotent checkpoint acceptance can be established from this packet.

SECTION 5 — TOP FIVE IMPROVEMENTS

These are ranked by practical value, not novelty.

Rank	Improvement	Category	Expected benefit	Effort	Regression risk	Dimensions	Priority
1	Exact manifest-to-result reconciliation and explicit final acceptance	Essential correctness	Prevents false-green batches and exposes missing/duplicate work	MEDIUM	Medium: changes success semantics intentionally	Reliability; trustworthy metrics	Immediately
2	Central validation and safe workflow input handling	Essential correctness/security	Rejects malformed manifests, escapes, duplicate IDs, invalid indices, and executable input interpolation	MEDIUM	Medium: previously accepted inputs may be rejected	Reliability, security, cost containment	Immediately
3	Output integrity: filename validation, staging, inventory, artifact verification; fix jpeg	Essential correctness	Prevents silent overwrite, hidden-output loss, and acceptance of incomplete outputs	MEDIUM	Medium	Reliability, reproducibility	Immediately
4	Reproducible end-to-end benchmark with locked environments	Evidence prerequisite	Determines whether any optimization improves actual useful completion	SMALL–MEDIUM	Low	Speed assessment, cost, reproducibility	Immediately, before architecture selection
5	Bounded multi-job shards; compare with an existing-resource warm worker prototype	Optional performance	Amortizes repeated setup for short tasks; quantifies whether persistent execution warrants complexity	MEDIUM	Medium: retry granularity and stragglers change	Speed, possibly cost	After items 1–4

A full rewrite is not justified. The visible correctness defects are repairable within the current workflow/runner boundary.

SECTION 6 — BENCHMARK VERDICT

Verdict: partially valid as an arithmetic comparison of your reported measurements; unverified as an equivalent-work performance comparison.

2003
/
292
≈
6.86.
2003/292≈6.86.

The workflows do not independently establish either measurement. More importantly, burst-benchmark.yml and burst-batch.yml exercise different orchestration paths:

Benchmark: four long-lived shard jobs, each invoking the missing benchmark script.

Production dispatcher: one matrix job per manifest item, plus setup, Pillow installation, per-item artifacts, and batch summary.

Consequently, the reported 2,003 tasks/minute must not be presented as measured throughput of arbitrary production manifest items.

Distortions requiring resolution
Issue	Evidence and implication
Task complexity	Comments assert identical SHA-256/zlib work, but the benchmark script and exact revisions are absent.
Startup exclusion	The benchmark's comments explicitly exclude queue/startup time from tasks/minute.
Concurrency	Four hosted shards are visible; VM concurrency is unknown. This may be a valid fleet comparison, not a per-resource comparison.
Retry behavior	Neither comparable retry counts nor unique operation identities are supplied.
Completion criteria	Benchmark aggregation trusts tasks_per_min; it does not validate completed-operation counts or outputs.
Missing/duplicate work	Expected shard identities are not reconciled.
Persistence	Artifact upload/download lies outside the script's internally reported rate unless the missing script proves otherwise.
Warm/cold state	VM and runner cache/process conditions are unknown.
Measurement windows	Summed shard rates are not automatically total work divided by a common end-to-end interval.
Resource equivalence	Host fields are printed, but live machine records, utilization, and VM specifications are absent.

Summing shard rates can be a meaningful estimate of concurrent steady-state capacity when work, timing, and concurrency align. It is not automatically a finite-batch makespan measurement.

Reproducible protocol

Freeze code, dependency versions, inputs, manifest, expected output digests, and random seeds.

Define a “task” precisely. Distinguish benchmark-loop iterations from production manifest items.

Use the same manifest on the VM, existing Actions dispatcher, bounded-shard variant, and optional warm-pool prototype.

Include representative image, hashing, text, and benchmark jobs; report each class separately.

Run:

Equal-concurrency comparisons to isolate orchestration/environment effects.

Available-capacity comparisons to evaluate practical fleet completion.

Separate cold and warm trials. Randomize trial order and repeat enough times to show variation.

Record timestamps for submission, scheduling, execution start/end, durable persistence, and validated acceptance.

Verify unique item identities and all declared output checksums.

Inject item failures, runner loss, cancellation, missing artifacts, and duplicate delivery.

Report distributions and unsuccessful runs, not just the best result.

Primary metric:

successful unique tasks/minute
=
60
×
validated unique successful items
seconds from submission to validated final acceptance
.
successful unique tasks/minute=
seconds from submission to validated final acceptance
60×validated unique successful items
	​

.

Also collect:

Failed, missing, duplicate, cancelled, and unresolved items.

Attempts and retries per item.

End-to-end latency: median, p95, and maximum.

Queue delay, runner startup, environment setup, execution, upload/download, and ingestion times.

CPU, memory, disk, and transferred bytes.

Actual billed usage and dollars per successful unique item.

Included/free allowance consumed, reported separately from incremental cash cost.

SECTION 7 — MINIMUM PATCH PLAN

This is an ordered change plan, not a replacement implementation.

Fix the immediate format defect.

File: tools/burst_runner.py

Function: job_image_convert()

Normalize jpeg; add tests for all documented formats.

Introduce one manifest validator used before fanout and execution.

Files: tools/burst_runner.py; .github/workflows/burst-batch.yml

Locations: main(), run_one(), setup manifest step.

Validate schema, supported types, unique safe IDs, parameter bounds, path policy, batch size, and nonnegative index bounds.

Define whether an empty batch is rejected or handled as a deliberate no-op; do not rely on matrix behavior.

Remove executable interpolation of dispatch inputs.

Files: both workflows.

Locations: setup Python, production execution shell, summary Python, benchmark execution shell.

Pass raw values through environment variables; validate before constructing paths or arguments.

Repair output correctness before adding retries.

File: tools/burst_runner.py

Functions: out_dir(), all file-producing handlers, main().

Reject duplicate/reserved filenames and escaping paths.

Use attempt-specific staging and atomic final result replacement.

Record output sizes and checksums; do not treat leftover attempt files as successful outputs.

Stream hashing and implement agreed resource bounds.

Make persisted results independently verifiable.

File: .github/workflows/burst-batch.yml

Locations: upload and download steps.

Establish an explicit hidden-file policy.

Validate required output files before upload; if-no-files-found: error alone cannot detect a missing result if other output files exist.

Download into separate artifact directories to prevent silent merge collisions.

Retain enough time for verified ingestion under an explicit retention policy.

Implement exact reconciliation and a truthful final outcome.

File: .github/workflows/burst-batch.yml

Locations: setup outputs, summary dependencies, summary Python.

Give summary the expected manifest identity and item set.

Reject wrong identities, duplicates, missing items, item errors, and missing/corrupt outputs.

Write/upload diagnostics before a final acceptance step sets failure status.

Preserve the distinction between item failure, infrastructure failure, and unresolved cancellation.

Repair measurement, then trial bounded sharding.

File: .github/workflows/burst-benchmark.yml

Location: shard inputs and summary.

Require all expected shard identities and successful-operation evidence; record end-to-end timing.

File: .github/workflows/burst-batch.yml

Trial a bounded group of indices per runner, retaining separate results and attempt directories for every item.

Add bounded retries only after persistence and idempotent ingestion are verified.

Pin dependencies and approved action revisions alongside these patches; do not combine an unnecessary architecture rewrite with correctness repairs.

SECTION 8 — CLAIMS REQUIRING VERIFICATION
Claim / unresolved question	Required evidence
Approximately 2,003 tasks/minute was observed	Original run URL/ID, complete shard JSON files, logs, commit SHA, and aggregation output.
Approximately 292 tasks/minute represents equivalent work	Baseline JSON, full invocation, script SHA, Python/zlib versions, VM specifications, process/thread counts, and timing logs.
Benchmark operations are valid and deterministic	Full tools/burst-benchmark.py, expected digests, iteration semantics, and output-validation logic.
Production throughput resembles the synthetic result	Representative manifests and end-to-end successful unique item counts from actual burst-batch runs.
Published runner specifications match these runs	Repository visibility/plan and run-level runner labels, image version, lscpu, memory, disk, and dependency-version output.
Available concurrency is sufficient	Account/organization concurrency configuration and actual run/job queue/start timestamps. GitHub's matrix size is not simultaneous capacity. 
docs.github

Queue jobs cannot disappear during packing	Full pack_batch.py, queue/checkpoint schema, transaction logic, and crash-recovery tests.
Checkpoint closure is idempotent	Full ingest_results.py, identity/digest checks, database constraints, commit sequence, duplicate-ingestion and crash tests.
Repeated dispatch is safe	Two runs of the same batch, artifact identities, ingestion logs, and resulting checkpoint state.
Rerunning failed jobs handles artifact names safely	Live rerun logs and artifact lists for the same run ID and changing attempt number. Upload v4 documents existing-name behavior; your exact rerun path must be tested. 
github

Artifact retention is adequate	Repository retention settings, retrieval schedule, failed-download recovery procedure, and measured ingestion delays.
Workflow permissions and secret exposure are acceptable	Repository/organization Actions policies, dispatch access controls, branch protections, environment rules, and available secret/token scopes.
API limits will not bottleneck ingestion	Ingest/dispatch request patterns, API response rate-limit headers, retry/backoff logs, and concurrent run volume.
Cancellation cannot close unfinished items	Cancellation/timeout/runner-loss test records plus ingester state transitions.
Free GPU lanes support this orchestration	Named providers, hardware, automation policies, session limits, networking, and an approved worker connection design.
One paid lane is actually guarded	Launcher/controller code, owner-approval mechanism, IAM restrictions, spend accounting, resource inventory, and shutdown test evidence.
$250 stop / $300 maximum prevents cash exposure	Credit terms/expiry, current accrued usage, reporting delay, worst-case in-flight liability, ancillary costs, and demonstrated shutdown enforcement.
A warm pool or sharding is materially faster	Repeated equivalent-work trials using the protocol above, including persistence, failures, and cost.
Environments are reproducible	Dependency lock data, action commit revisions, image/runtime identifiers, and repeated output-digest comparisons.

Useful collected run data would include the equivalents of:

text
gh run view RUN_ID --json status,conclusion,createdAt,startedAt,updatedAt,jobs
gh run view RUN_ID --log
gh api repos/OWNER/REPO/actions/runs/RUN_ID/artifacts

These are evidence-collection suggestions, not commands I executed.

SECTION 9 — FINAL DECISION

A. Keep the current architecture and patch it.

The evidence supports repair, not replacement:

The current design is understandable and suitable for bounded CPU burst work.

Its most consequential defects are in validation, output integrity, reconciliation, and success reporting—not an irreparable scheduling model.

The 6.86× figure does not establish production-item throughput or superiority over a warm pool.

No alternative has demonstrated better end-to-end performance on equivalent work within your actual resource and financial constraints.

Deploying a new fleet before fixing result acceptance would distribute the same correctness problems across a more complex system.

Challenge the present assumption that one small item deserves one fresh runner. Test bounded multi-item shards first, then a persistent worker-pool prototype using existing approved resources. Promote that pool to a complementary architecture only if measured gains survive output verification, retries, failures, and cost accounting.

Until then, no new paid infrastructure, no broader fanout justified by the synthetic benchmark, and no checkpoint closure based solely on workflow success.

30 sources
Show me how to fix the false-green completion bug
Walk me through patching the artifact overwriting defect
Draft the lease-based worker pool architecture test
How should we benchmark the multi-job sharding strategy
Help me write a strict manifest reconciliation check
⠦




Ask a follow-up
Search
Computer
Model
Cookie Policy

We and our partners use cookies, pixels, SDKs, APIs, and server-to-server integrations. Perplexity does not use these technologies to sell third party ads on our services. Perplexity uses them to measure our ad performance on third party partner websites and to improve our services. If you continue using Perplexity, without adjusting your settings, you are consenting to these technologies.

Cookie Policy
We and our partners use cookies, pixels, SDKs, APIs, and server-to-server integrations. Perplexity does not use these technologies to sell third party ads on our services. Perplexity uses them to measure our ad performance on third party partner websites and to improve our services. If you continue using Perplexity, without adjusting your settings, you are consenting to these technologies.
Decline optional
Got it
