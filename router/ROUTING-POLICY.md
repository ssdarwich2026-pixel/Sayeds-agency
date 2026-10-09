# Routing Policy — how the agency picks a model for a job

## The question
"For this task, what is the best available model/tool right now?" — answered
against `registry/models.yaml`, not a hard-coded list.

## Priority order
1. **Free/open first.** `free-tier`, `open-weights`, `local` entries are the
   default routes (`agency-chat`, `agency-strategy`, `agency-copy`,
   `agency-code`, `agency-local`).
2. **Fallbacks, not failures.** Every route has fallbacks in the LiteLLM
   config. If a provider is throttled or down, the router moves — the job
   doesn't die.
3. **Paid is gated.** `agency-premium` (and any future paid route) NEVER runs
   without Sayed's explicit approval for that spend. The worker surfaces
   "paid route would help here: <cost estimate>" and waits.

## Task → route mapping
| Task | Route |
|---|---|
| General crew work, research, analysis | agency-chat |
| Strategy, pricing, hard reasoning, judging councils | agency-strategy |
| Copy, captions, reports, listings | agency-copy |
| Code, automation, repo work | agency-code |
| Cheap summarization, private/local work | agency-local |
| "Free models aren't sharp enough for this" | agency-premium (GATED) |

## Review councils
Important outputs go through N-model critique via different routes
(e.g. skeptic on agency-strategy, copy editor on agency-copy, analyst on
agency-chat). Merge rule: keep changes 2+ critics agree on, plus the single
highest-leverage solo fix. Sayed's draft approval is the final council seat.

## What the router never does
- Spend money without approval.
- Lock the agency to one provider.
- Trust a single model's output on anything public-facing.
