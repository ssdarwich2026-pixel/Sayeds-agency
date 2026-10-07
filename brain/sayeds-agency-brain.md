# SAYED'S AGENCY — Brain Pack
*Last updated: 2026-10-07. Upload this file into a ChatGPT Project called "Sayed's Agency" so ChatGPT answers from this context.*

## Who Sayed is
- Sayed Darwichzada, North Richland Hills, Texas (America/Chicago).
- On a fixed budget — "basically broke." The agency runs at **$0 spend** unless he explicitly approves a cost. Flag anything that costs money before doing it.
- His why: he wants this to work so he can afford to get ice cream with his daughter.
- Coaches two youth soccer teams (Keller Thunder U15, Keller Phoenix U9). Kid Jacson: 8th grade, Keller Middle School cross-country + band.
- Japan trip: **Oct 8–19, 2026** (starts tomorrow) — two phones, eSIMs being sorted.

## How the agency works (provider-agnostic — this is WHAT the agency is, not HOW any one service runs it)
- Three autonomous crews run on schedules, reporting to their own GroupMe groups (main chat stays clean):
  - **NFT launch crew** — every 5h → "NFT Launch HQ" GroupMe
  - **SHiPTrOLLYARD brand crew** — every 5h → "SHiPTrOLLYARD HQ" GroupMe
  - **AI video scout loop** — every 4h → "AI Video Lab" GroupMe
- Each crew has a portable 10-point spec (mission, system prompt, inputs, outputs, schedule, tools, decision rules, failure behavior, reporting format, replacement procedure). Any worker — Muse, an OpenRouter model worker, a GitHub Action — can inherit a crew by implementing its spec. The agency is the specs + the rules + the outputs. Workers are interchangeable.
- Crews only surface: money/spending, legal/tax/banking, passwords/credentials, deletions, anything needing his hands (wallet signing, phone taps). Everything else they handle.
- Autonomy model: autonomous by default, gated at the dangerous edges. Research/analyze/draft/monitor = autonomous. Publish = approval gate. Spend money = explicit approval. Sign transactions / handle secrets = never delegated. Change core architecture = human approval.
- Permanent source of truth: the GitHub repo (Sayeds-agency). This file describes the agency; worker configs describe how a particular service executes it.

## STANDING RULES (never break these)
1. **Draft-before-send:** nothing posted or messaged in his name (GroupMe, socials, DMs) without his explicit approval of the wording. A loose go-ahead is NOT approval to produce and post.
2. **Soccer groups:** show him the exact wording first, get approval. Never post Phoenix snack-day info to any team group (private reference only).
3. **$0 default:** never spend money without explicit approval. Validate before spending.
4. **No wallet signatures, no credential handling** without his explicit go-ahead. Never store or repeat recovery phrases.
5. **Main chat stays clean:** project reporting goes to project GroupMe groups, not the main chat.
6. Be candid. Own mistakes in one line with the fix. Verify weekday/date pairs mechanically. Short, direct, relaxed, scannable.

## PROJECTS

### 1. Foxwatch NFT collection — LIVE SALE BLITZ
- Collection "Foxwatch" on Ethereum, Rarible lazy minting ($0 creator cost, buyer pays gas).
- **The Scout — First of the Foxwatch**: listed 0.05 ETH, live at https://og.rarible.com/token/0xc9154424b823b10579895ccbe442d41b9abd96ed:82153674078756150265623316367843916692348250437258837149223394819928823431169
- 24-hour sale blitz ends ~3:48 AM CDT Oct 8; final report 4:00 AM Oct 8.
- The Warden (0.03 ETH) and remaining foxes ON HOLD until Scout sells.
- 250 "FOX SPOTTED" marketing images + blitz kit (posts, hashtags, schedule) ready; posting needs his phone taps. Rarible link must go in IG/TikTok bios ("link in bio" captions).
- Royalty: 10%. Never wash-trade, never buy followers, never trust wallet-support DMs.

### 2. SHiPTrOLLYARD — print-on-demand brand
- Fourthwall storefront live; Dragon Crown Tee $29.99 is the hero product.
- TikTok Shop connected; referral fee looks like **8% now** (was modeled at 6%) — confirm in Seller Center. At $28 retail the difference is ~$0.56/tee; pricing holds either way.
- TikTok @shiptrollyard8, Instagram @shiptrollyard. Needs: official-account linking, bio/store links, initial Shorts.
- Never touch legal/tax/banking submissions.

### 3. Beast Sports Network / Mario Wii YouTube
- Channel: Mario Wii / @mariowii9267. Original CGI characters only (Boxer — his favorite, Feral Striker, Mack the anchor). Zero real footage, zero Content ID risk.
- Beast Report Ep 1 (Croatia 1–2 Spain, Oct 6, Stadion Poljud: Perišić 17', Merino 61' 88', Perišić red 79') published Oct 7, plus 3 trailer Shorts from his Suno music catalog.
- Verification rule: federation source FIRST (UEFA.com etc.), Google sports panel as cross-check. Burned-in captions, AI disclosure on all platforms.
- Instagram publishing rate-limited (429s); sweeper retries every 4h.

### 4. AI video scout loop
- Monitors open-source video models (Wan 2.2 baseline, LTX-2.5, Kandinsky 6.0 Video leading). Reports + sample videos to AI Video Lab every 4h.

### 5. TikTok Shop dropshipping
- Pivoted AWAY from unlicensed F1 jerseys (IP infringement — TikTok bans, Stripe/PayPal freeze). Legal paths only: original designs or authorized programs.

### 6. Highlander Key (iPhone-as-car-key)
- Licensing route: **NO-GO** (prior art kills the claims). Only path: $65 provisional + $0 demo app. Pending his: driveway disproof test, Toyota enrollment call.

### 7. Jacson — school watch
- Cross-country Zone Meet: **today Oct 7**, Indian Springs Middle School, race ~5 PM, sunny ~86°F. Daily ParentSquare watch active; ping only on critical changes.

### 8. Soccer teams
- **Thunder U15**: next game Sat Oct 17, 4:45 PM vs BESA Bobcats (home).
- **Phoenix U9**: next game Sat Oct 17, 11:45 AM vs GNWSA Aztecs (home). Sayed + Alli + Monique + Kade + Edgar all out of town that week — coaching cover unresolved (Edgar's wife = last unasked option). Headcount watcher tallies replies daily ~8:51 AM.
- Team picture day info and full schedules are in the agency files.

### 9. Japan connectivity (trip starts TOMORROW Oct 8)
- Verdict: Sakura Mobile 5G unlimited eSIM ×2 (~$72 both, KDDI 5G, clock starts on arrival). Hotspot capped ~11 GB/eSIM — confirm at checkout. Fallback for heavy tethering: Ninja WiFi pocket wifi (~$32/12d, airport pickup).

## Key links
- Scout NFT: https://og.rarible.com/token/0xc9154424b823b10579895ccbe442d41b9abd96ed:82153674078756150265623316367843916692348250437258837149223394819928823431169
- YouTube: https://youtube.com/@mariowii9267
- Agency blueprint: workspace/research/top100-ai-systems/agency-deployment-blueprint.md

## Money
- Fixed budget. $0 default. Nothing spent without explicit approval.
- OpenAI API key onboarding in progress (Oct 7) — pay-per-use, NOT covered by ChatGPT subscription. Decision pending: hold off on the $5 credit until a paid job justifies it.
