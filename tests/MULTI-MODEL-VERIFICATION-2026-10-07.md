# Agency Multi-Model Verification — Baseline (2026-10-07)

**Result: 9/12 PASS — 21 free API calls, $0.00 spent.** No paid routes touched,
no config changed to pass, no credentials exposed. Full machine-readable results:
`verification-results-2026-10-07.json` + `retest-results.json`.

## Scorecard

| # | Test | Verdict | Models used | Route | Fallback | Verified |
|---|---|---|---|---|---|---|
| 1 | Strategy | PASS | nemotron-3-ultra-550b:free | agency-strategy | none needed | n/a |
| 2 | Writing/Copy | FAIL | nemotron-3.5-lightning:free | agency-copy | none needed | n/a |
| 3 | Analysis/Reasoning | PASS | gemma-4-31b-it:free | agency-strategy | none needed | n/a |
| 4 | General Chat | FAIL | apodex-1.1-mini, lfm-2.5 (both empty) | agency-chat | 2 tried | n/a |
| 5 | Multiple Models | PASS | ultra + lightning (+gemma4 flaky) | 3 routes | n/a | n/a |
| 6 | Router Decision | PASS | — (decision only) | route.py | n/a | n/a |
| 7 | Fallback | PASS | bogus→lightning | agency-chat | auto, no human | n/a |
| 8 | Verification | FAIL | ultra → lightning | strategy→chat | n/a | NO |
| 9 | Crew Handoff | PASS | lightning (via nft-launch SPEC) | SPEC→router→worker | none needed | n/a |
| 10 | Registry | PASS | — (audit) | registry/models.yaml | n/a | n/a |
| 11 | Cost/Safety | PASS | — (audit) | n/a | n/a | n/a |
| 12 | End-to-End | PASS | lightning → ultra | brain→crew→router→model→verify→report | n/a | YES |

## What the failures actually mean

- **#2, #8 — output discipline, not plumbing.** The free reasoning models dump
  chain-of-thought ("Here's a thinking process…") instead of following strict
  format instructions, even with "OUTPUT ONLY" directives. Calls succeed;
  outputs need post-processing or non-reasoning models for format-strict jobs.
- **#4 — dud models exist.** Two small free chat models returned empty content
  through the API. The router's fallback chain is the answer, not any single model.
- **Real-world flakiness observed:** gemma-4-26b:free and laguna-s-2.1:free hit
  upstream shared-pool 429s; qwen3.8-27b:free lost its free tier entirely
  (now deprecated in the registry). Free availability churns — the scout exists
  for exactly this.

## Weaknesses discovered

1. Reasoning-model verbosity breaks format-strict tasks (copy, verification verdicts).
2. Free-model roster churns weekly; hard-coding model IDs anywhere would rot.
3. 50 req/day free budget is the real ceiling — councils with N parallel models
   must budget calls or they starve mid-day.

## Recommended improvements (no architecture change)

1. Prefer non-reasoning free models for format-strict outputs; reserve reasoning
   models for analysis/strategy.
2. Add a "strip thinking" post-processor to the openrouter skill for strict tasks.
3. Keep model IDs resolving through the registry/scout only — never hard-code.
4. Budget free calls per crew run; fall back to orchestrator when budget is low.

## Conclusion

The agency is genuinely multi-model and fault-tolerant: different tasks route to
different models, fallbacks fire automatically, verification runs model-to-model,
and the full loop executes end-to-end at $0. It is not "an OpenRouter connection
that happens to work."
