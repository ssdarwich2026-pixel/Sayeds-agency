# Model & Tool Registry — maintenance contract

`models.yaml` is the agency's living pool of models and tools. It is maintained
by the **daily AI Ecosystem Scout** (`automations/ai-ecosystem-scout/`), not by
hand-editing between scout runs (emergency corrections excepted).

## Rules for the scout
1. **Add, don't replace.** New verified models get new entries. Never delete an
   entry to make room — move dead ones to `deprecated:` with reason + date.
2. **Verify before listing.** An entry needs a weights URL, a live demo, or a
   working API — rumors don't get entries.
3. **Refresh `last_verified`.** Touch every entry you re-confirmed; anything
   older than 30 days gets flagged for re-verification in the scout report.
4. **License first.** Every entry carries its license and commercial-safety
   status. Research-only weights are marked DO NOT USE for commercial work.
5. **Free-first ordering.** `access: free-tier | open-weights | local` entries
   are preferred routes. `paid-api` entries are NEVER default routes without
   Sayed's explicit approval — they sit in the registry as options, gated.
6. **No loyalty.** The registry serves "best tool for the job," not a provider.

## For workers
Read this registry (via the router) when choosing a model for a task. If the
registry doesn't have what you need, say so in your report — that's the
scout's job to fix, not yours to hack around.
