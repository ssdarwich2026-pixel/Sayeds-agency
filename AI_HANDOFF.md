# AI Agent Handoff — Sayed's Agency

> **Read this first.** You are picking up work for Sayed Darwichzada's one-man agency.
> This repo is the permanent source of truth. It is public and free — that's the point:
> any AI agent (Muse, ChatGPT, or otherwise) can read it cold and continue the work,
> especially when the primary agent is paused due to token/funding limits.

## The setup

- **Sayed** is the owner. He is traveling in Japan Oct 8–19, 2026, with limited phone data.
- **ChatGPT** ($8 plan) is PRIMARY: planning, decisions, drafts, advice.
- **Muse** (free tier) is SECONDARY: execution back office — crews, schedules, files, posts.
- Sayed is the bridge between them. This repo is the shared brain both sides read.
- **Budget: $0 means $0.** Flag every cost before acting. No spending without Sayed's explicit approval.

## Current mode: HIBERNATION (since 2026-10-10 JST)

Free-tier tokens are scarce. All non-NFT crews are **disabled, not deleted**.
To resume everything: re-enable the 4 paused crons (see below) and confirm.

### Paused (one toggle each to resume)
| Cron job | Cadence | What it did |
|---|---|---|
| `ai-video-scout-loop` | every 4h | Open-source AI video model scouting |
| `shiptrollyard-crew` | every 5h | SHiPTrOLLYARD brand crew |
| `daily-open-source-sweep` | daily | Open-source AI tools sweep |
| `ai-ecosystem-scout` | daily | AI ecosystem scout |

### Still running
- `nft-launch-crew` (every 5h) — the focus project, see below
- `jacson-school-watch` (daily) — his kid's school updates. Family. Never pause.
- `oct17-headcount-watch` / `oct17-headcount-final` — youth soccer, time-bound to Oct 17
- `avatar-shades-rotation` (daily) — tiny, his standing request
- `agency-bot-health-watch` (every 6h) — dead-man's switch for the GroupMe bot

## The active project: Foxwatch NFTs (ALL effort goes here)

- **Collection:** Foxwatch — original fox-ranger characters, Rarible lazy minting (buyer pays gas, $0 upfront), 10% royalty.
- **Live:** "The Scout — First of the Foxwatch", 1/1 at 0.05 ETH. Listed, not sold, no bids (as of Oct 9).
- **Staged:** 54 additional pieces, full metadata (names, descriptions, traits, price tiers) in `projects/nft-launch/foxwatch-batch2-metadata.json`. 44 standard / 9 premium / 1 skip.
- **Art files:** 54 PNGs (512×512) in Sayed's Google Drive "Fox" folder (shared link — ask Sayed; not in this repo due to size).
- **Strategy:** EDITIONS, not 1/1s — 54 artworks × 100 editions each = ~5,400 low-priced tokens from 54 signatures. $0 path to volume. (A true 5,000-piece generative mint needs a paid smart contract + gas — rejected under $0 rule.)
- **Revenue target:** $500/week from NFTs alone (Sayed's goal). Near-term survival math: ~8 edition sales/month at ~$13 covers operating costs.
- **Blocked on Sayed only:** curate 12–15 pieces for first drop + one MetaMask signing sitting (Rarible = 1 signature per listing). He holds the wallet; never ask for seed phrases.

## Operating rules (load-bearing)

1. **Draft-before-send:** nothing posts or messages in Sayed's name without his exact wording approval. (Exception: the AI video crew's autonomous reels, currently paused.)
2. **$0 means $0.** No spending, no paid tiers, no gas fees without explicit approval.
3. **No architecture changes** without Sayed's explicit approval (OPERATE mode).
4. **GroupMe session is expired** (web login lapsed; needs his manual Apple-tap re-sign-in). Crew reports can't post until then. Never enter passwords.
5. **Token-lean:** batched work, short outputs, no multi-agent blitzes unless the payoff justifies it.

## First actions for the picking-up agent

1. Read `projects/nft-launch/` for the latest status and the batch-2 metadata.
2. Check `runs/` for the most recent crew run notes.
3. Continue the NFT work: the next step is always the same — move pieces toward listing and sales with $0 spend.
4. If Sayed says "we're back" (funding resumed): re-enable the 4 paused crons, verify health, report fully operational.

## Key links

- Repo: `https://github.com/ssdarwich2026-pixel/Sayeds-agency`
- Rarible collection: Foxwatch (The Scout live)
- Instagram: `@shiptrollyard`, `@todaytomorrowyesterday531` — future fox-character content engine
