# Jury of Five — Tier-1 Executive Council

A light multi-model council for everyday agency questions. One question goes
to five free OpenRouter models in parallel (identical neutral prompt); a judge
call then synthesizes a single **VERDICT** — the consensus/best answer, where
the five disagreed and how it was resolved, a confidence note, and an
**ESCALATION** decision: whether the question should go up to tier 2, the
In-Depth Crew (the full 45-model deep review, not yet built), with a draft
escalation packet when it should.

Tier 2 is deliberately *not* part of this build. This jury's escalation block
is the hand-off point: it drafts the refined question + findings + open
disagreements the crew would start from.

## Run it

```sh
cd ~/workspace/agency/council
python3 jury.py run "Your question here"
python3 jury.py probe        # reachability-check the five seats + fallbacks
```

Every run is logged to `runs/` as markdown (question, all five answers with
model IDs, the verdict, and the exact request count).

## The Five (verified live at $0 on 2026-10-20)

| Seat | Model | Provider | Why this seat |
|---|---|---|---|
| A | `nvidia/nemotron-3-ultra-550b-a55b:free` | NVIDIA | Strongest strategist in the free pool (550B MoE); registry lists it for strategy/hard reasoning; also serves as judge (below) |
| B | `google/gemma-4-31b-it:free` | Google | Provider diversity; solid general analysis. Upstream 429-prone — the runner retries and recalls it, and a run proceeds without it if it stays dark |
| C | `xingchen-agi/xing4.0-29b-a4b:free` | Xingchen AGI | General reasoning; clean, complete answers in probes and runs. **Not yet in the registry — flagged for the ecosystem scout to add** (the seat it replaced, MiniMax, is in nobody's registry either; see swaps) |
| D | `dots-studio/dots-3-note-preview:free` | Dots Studio | Passed the agency's strict-JSON gate live on 2026-10-08; structured, disciplined answers |
| E | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` | NVIDIA | Dedicated reasoning model; a second NVIDIA seat because today's $0 catalog is NVIDIA-heavy and the non-NVIDIA alternatives were gated, broken, or empty (below) |

**Judge: Nemotron 3 Ultra (seat A's model).** It is the only model in the
registry with `format_strict_ok: true` — exactly what a fixed-section verdict
needs — and the strongest reasoner of the five. A sixth, distinct judge would
cost the same 1 call, so a separate judge only makes sense if it's *better*;
no unverified free model is. The judge sees the five answers labeled by letter
and provider only (model IDs hidden) to blunt self-preference.

## Reachability evidence (all probes were real OpenRouter calls, 2026-10-20)

Candidates probed with a minimal prompt, then with real juror prompts:

- ✅ Ultra 550B, Gemma 4 31B, Dots 3 Note, Nano-Omni 30B, Xing 4.0 — answered.
- ❌ **Thinking Machines Inkling** — HTTP 403: free endpoint is gated to
  "agentic harnesses" only (matches the registry note). Not usable.
- ❌ **Nemotron 3 Super 120B** — HTTP 404 from the provider function, twice.
  Agency-verified on 2026-10-08, broken today. Listed as a fallback to retest.
- ❌ **MiniMax M3.1 Flash** — reachable and clean on a one-word probe, but on
  real prompts its hidden reasoning consumed all 1,100 completion tokens and
  returned *empty content* (verified in the raw response: 1,100/1,100
  reasoning tokens, finish_reason=length). Swapped out for Xing 4.0; kept in
  `fallbacks` with the caveat that it needs a much larger token budget.
- ⚠️ **Nemotron 3.5 Lightning** — returned empty content even at 200 tokens.
  Excluded.
- ⚠️ **Gemma 4 26B** — 429 at every probe. Fallback only, retest before use.

## Free-tier limits actually hit (this is the honest operating picture)

- **Shared-pool 429s are the norm, not the exception** (Google AI Studio and
  Phala pools especially). Mitigations in `jury.py`: staggered juror starts
  (a simultaneous burst tripped NVIDIA's "worker local total request limit
  reached (16/16)" concurrency cap), one retry per call, then a sequential
  **recall pass** for failed jurors after a cooldown. A run proceeds with
  ≥3 of 5 answers and logs every failure.
- **HTTP 200 with an error body** happens (NVIDIA pools) — the runner checks
  for a missing `choices` key instead of crashing.
- The canonical sample run (below) seated 3 of 5 jurors (A, D, E) after
  Gemma and Xing were rate-limited through every retry. The verdict is still
  complete — but treat "five" as the design, "three-plus" as a bad-day floor.

## Budget

~50 free OpenRouter requests/day, shared agency-wide. A clean jury run costs
**6 requests** (5 jurors + 1 judge); a rough free-tier day costs more
(retries + recalls — the sample run cost 14). `jury.py` checks the budget
before fan-out (`budget.py check`) and records every attempt. Practical
capacity: roughly 3–7 jury runs/day depending on pool weather. Tier-1 is for
everyday questions; don't burn the day's budget on trivia.

## Files

- `jury.py` — the runner (config-driven, stdlib + PyYAML only)
- `config.yaml` — the five, the judge, prompts, fallbacks, limits
- `runs/` — one markdown log per run

## Maintenance notes (found during the build)

- The connector's legacy `chat.py` is currently broken: it imports
  `dynamic_credentials` from a path that no longer exists
  (`.../custom-connector-setup/templates/skill/bin/`). The module now lives in
  `/opt/muse/skills/custom-connector-setup/bin/`. `jury.py` searches both
  paths. `chat.py` itself was left untouched — fixing it is a separate call.
- `budget.py record` is not safe under parallel calls (concurrent
  read-modify-write lost counts during probing; the 2026-10-20 counter was
  reconciled by hand to the true attempt count). `jury.py` records serially
  from its main thread.
- Two seats (Xing 4.0 live-verified today; MiniMax evaluated and rejected)
  are registry news — the ecosystem scout should fold them into
  `registry/models.yaml` on its next pass.
