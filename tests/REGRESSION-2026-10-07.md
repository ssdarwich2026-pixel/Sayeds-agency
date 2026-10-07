# Production Hardening — Regression Test (2026-10-07)

**Result: 3/3 PASS — 2 free API calls, $0.00 spent.** Approved rules implemented;
no other architectural changes.

## What was implemented

1. **Strict-format routing** — `registry/models.yaml` carries `format_strict_ok`
   per model (ultra: true, lightning: false — from hardening evidence);
   `registry/README.md` tells the scout to format-test new models;
   `router/route.py strict` resolves dynamically to the verified model.
2. **Production quality gate** — `chat.py --gate json|schema|max-words:N`;
   unusable outputs exit 4 (failed execution) so callers trigger the existing
   bounded fallback instead of passing garbage downstream.
3. **Budget-aware fan-out** — `bin/budget.py` tracks daily free calls
   (date-keyed, 50/day); `chat.py` records every attempt; `budget.py check N`
   refuses oversized fan-outs. Skill SKILL.md documents all three rules.

## Regression results

| Rule | Test | Result |
|---|---|---|
| 1 | `route.py strict` selects format-verified model | PASS — nemotron-3-ultra-550b, available → executable |
| 2a | gate rejects CoT-leaking model on JSON task | PASS — exit 4, reason: chain-of-thought leaked |
| 2b | gate passes clean model on JSON task | PASS — exit 0, `{"ok": true}` |
| 3a | 100-call fan-out with 48 remaining | PASS — refused, exit 1 |
| 3b | 3-call fan-out with 48 remaining | PASS — allowed |
| 3c | calls auto-recorded | PASS — used=2 after 2 calls |

## Preserved

$0 default · paid routes gated · bounded retries · secure credentials
(vault surrogate, never exposed) · architecture freeze · provider/model
independence · scout/registry process unchanged.
