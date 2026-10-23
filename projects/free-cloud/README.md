# free-cloud adapters — Expansion order: Supabase, Upstash, Groq, Render, Hugging Face

A service counts as EXPANDED only with all four evidences: account
under Sayed's identity, adapter code with a passing cage test, a live
health check, one real gated smoke task. Anything less is QUEUED or
UNVERIFIED (FREE-CLOUD-EXPANSION-7000 spec, 2026-10-23).

Status (2026-10-23 upgrade window, Agent 81):
- Supabase: adapter BUILT with local stand-in cage tests green.
  Account/project creation is Sayed's one GitHub-OAuth tap in the
  batched sitting (VERIFY-LATER) - until then state = UNVERIFIED,
  adapter runs against the stand-in only. No card asked at signup
  per the provider's free tier as documented in the W1 sweep spec.
- Upstash / Groq / Render / Hugging Face: QUEUED in that order;
  adapters land in later upgrade windows. A service that demands a
  card at signup gets marked CARD-GATED and the next reserve takes
  its slot; no payment details are ever entered.
