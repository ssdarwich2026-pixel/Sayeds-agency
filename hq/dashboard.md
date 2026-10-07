# HQ Dashboard — the office window

One page: every project, every crew, what ran last, what's next — and the only
things that need Sayed's hands. Regenerated after every crew run.
Main chat stays clean; this page is pull (he checks when he wants).

*Last updated: 2026-10-07 (GroupMe office is LIVE — bot polling every 5 min via GitHub Actions)*

---

## 🚨 Incident log

- **2026-10-07 ~01:00 CDT — poller re-answer spam:** the "commit poll state" workflow step was failing on the runner, so no state persisted between runs and the bot re-answered old messages ("I don't know" spam). Fixed: state now persists via actions/cache; added first-run catch-up (old chatter marked seen without reply, real commands still answered). 51/51 poll tests + 23/23 dry-run tests green. Dead-man's-switch cron `agency-bot-health-watch` (every 6h) now guards the schedule.

---

## Project status

| Project | Status | Note |
|---|---|---|
| Fox-ranger NFT launch | 🟡 needs Sayed | Milestones Oct 7–10; wallet setup is his tap |
| SHiPTrOLLYARD brand | 🟢 on track | Crews auditing; TikTok account link is his tap |
| Beast Sports Network | 🟡 needs Sayed | Direction locked; crew starts on his word |
| AI video lab | 🟢 on track | Scout loop running every 4h |
| Dropshipping research | 🟡 needs Sayed | Crew starts on his word |
| Highlander key | 🟡 needs Sayed | Driveway test + Toyota call are his moves |
| Jacson school watch | 🟢 on track | Daily ParentSquare check running |
| Soccer teams | 🟢 on track | All remaining games on the GroupMe calendars |

---

## Crews — last run / next run

| Crew | Schedule | Last run | Result | Next |
|---|---|---|---|---|
| nft-launch | 5h | — | — | on Sayed's go |
| shiptrollyard | 5h | — | — | on Sayed's go |
| ai-video-scout | 4h | 2026-10-06 | report + sample video to AI Video Lab | +4h |
| jacson-watch | daily | 2026-10-06 | — | daily |

*(Existing workspace crons keep running until the repo + Actions take over.)*

---

## Review councils — latest verdicts

No councils run yet. First live council proposed: **NFT launch listing**
(`councils/review-council.yaml` is the starter config).

---

## Sayed's action queue — the ONLY things needing his hands

1. **Review the deployment blueprint** (`research/top100-ai-systems/agency-deployment-blueprint.md`) — draft v1, your call on all of it.
2. **GroupMe bot go-live** (3 taps): create the bot at dev.groupme.com → host the server (VPS or free tunnel) → set the callback URL. Guide: `integrations/groupme-bot/README.md`.
3. **Create the empty `sayeds-agency` repo** on GitHub (account: `ssdarwich2026-pixel`) — then the push commands go out.
4. **OpenRouter key** (openrouter.ai, ~3 min) — unlocks 400+ models through one key.
5. **Machine decision** — $5/mo VPS or your own PC running Ollama free (doubles as the bot host).
6. **NFT milestones** — Oct 7 wallet, Oct 8 name/prices, Oct 9 list, Oct 10 announce (all 6 PM CDT).

Everything else runs without you. That's the point of the office.
