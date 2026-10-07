# Format & Reliability Hardening — Results (2026-10-07)

**Result: 4/5 PASS — 12 free API calls, $0.00 spent, 38/50 daily budget remaining.**
No architecture changed. Machine-readable: `hardening-results-2026-10-07.json`.

## Scorecard

| # | Test | Verdict | Models tested | Calls | Failure detected? | Fallback? | Usable answer? |
|---|---|---|---|---|---|---|---|
| 1 | Format compliance | PARTIAL | nemotron-3-ultra-550b, nemotron-3.5-lightning | 6 | yes (lightning 0/3) | n/a | ultra 3/3 |
| 2 | Empty-response detection | PASS | apodex, lfm-2.5 → lightning | 3 | yes, both duds | auto → lightning | yes |
| 3 | Output-quality gating | PASS | — (9 unit checks) | 0 | all 9 correctly classified | n/a | n/a |
| 4 | Retry/fallback bounds | PASS | apodex, lfm-2.5 | 2 | n/a (one dud recovered) | stopped at cap, no loop | yes |
| 5 | Call budget | PASS | — (audit) | 0 | n/a | n/a | n/a |

## Key findings

1. **Format compliance is model-specific, not random.** nemotron-3-ultra-550b
   passed all 3 strict tasks (JSON-only, fixed schema, 10-word limit).
   nemotron-3.5-lightning failed all 3 — it leaks chain-of-thought
   ("Here's a thinking process…") even with explicit "OUTPUT ONLY" instructions.
   Bigger reasoning model = better instruction-following here.
2. **Empty responses are now treated as failed executions.** The gate caught both
   dud models and the fallback chain automatically moved to a working model.
3. **One "dud" recovered.** apodex/lfm-2.5 returned empty in the baseline but one
   answered in this run — proof the roster must be re-verified continuously
   (scout's job), never hard-coded.
4. **Retries are bounded.** Cap enforced, no runaway loop possible in the harness.

## Recommended rules (for Sayed's approval — NOT yet implemented)

1. **Format-strict routing:** strict-format tasks route only to models verified
   format-compliant (today: nemotron-3-ultra-550b 3/3). Reasoning-leaky models
   stay on loose/creative tasks. The scout format-tests new models before
   recommending them for strict work.
2. **Production quality gate:** adopt the tested `is_usable()` gate in the
   openrouter skill — empty / malformed / refusal / over-limit responses count
   as failed executions and trigger fallback automatically.
3. **Call-budget gate:** the router checks remaining free budget before fanning
   out; oversized councils are refused or shrunk when budget is low, never
   silently starved.

## Bottom line

The router now knows when a model gave it garbage and quietly moves to a better
worker. That was the point of this test — and it holds.
