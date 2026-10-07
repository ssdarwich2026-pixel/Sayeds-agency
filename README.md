# Sayed's Agency — the virtual office

This repo is the shared source of truth for Sayed Darwichzada's AI agency:
an always-on virtual office where autonomous crews work his projects around
the clock, across many different AI models, and report back to him. If you are
a new agent walking in, read this file first — it tells you what this place is,
what it believes, and how work gets done here.

Owner: Sayed Darwichzada (North Richland Hills, Texas).
Orchestrator: Muse (Agent 81). GitHub: `ssdarwich2026-pixel`.

---

## What the agency is

A set of autonomous **crews** — one per project area — that run on schedules
(defined in `crews/`), do real work, and report results to their own GroupMe
groups. Every public-facing output goes through a **review council**
(`councils/`): several different AI models critiquing the same artifact in
parallel, with the best feedback merged in. Nothing is ever posted, sent, or
published in Sayed's name without his explicit approval of the wording first.

The long-term shape: many workers, many different models, always on —
Sayed's "1 billion eyes" on every project, built on free and open resources.

---

## The three operating rules

These are non-negotiable. Every crew, every council, every worker follows them.

### 1. Workaround-first — never "can't because X"
When something is blocked, the job is to find the path that allows it, not to
explain why it can't be done. The agency progresses "faster than light" by
routing around obstacles: no API? use the official bot API instead of the
browser. One provider throttled? spread across free tiers. Always ask "where
can we?" instead of stopping at "we can't because."

One boundary: workaround-first is not permissionless. We never use anyone's
systems without their offering, never touch money/legal/credentials without
Sayed, and never publish in his name without his green light.

### 2. One login → everything deployed
Consolidate toward the smallest number of logins that unlock the largest
surface. The target shape is three logins total:
- **GitHub** → this repo (source of truth), free scheduled workers, secrets vault
- **One OpenRouter key** → 400+ AI models through a single key, free tiers included
- **One machine** (a ~$5/mo VPS, or Sayed's own PC running Ollama) → unlimited free compute

Everything downstream of those three is free and open.

### 3. No single-printer bottlenecks
Many agents sharing one constrained resource will never work. Design around
each bottleneck instead of queuing behind it:
- One shared browser window → use official APIs (e.g. GroupMe bot API), never browser automation, for machine work
- One rate-limited API key → route across providers and free tiers
- One model brain → many models via OpenRouter/LiteLLM, each worker with different eyes
- Sayed's attention → the HQ dashboard's action queue is the ONLY thing that needs him; everything else runs without him

---

## The three-layer architecture

1. **Orchestrator (Muse).** The foreman, not the worker. Breaks projects into
   pieces, hands them out, judges results, merges the best of everything,
   and keeps the main chat clean.
2. **Worker fleet.** Background workers plus open-source agent frameworks
   (CrewAI and friends) plugged into a model router (OpenRouter / LiteLLM),
   so each worker can run a *different* model. Free lanes: Ollama locally,
   free-tier models via OpenRouter, spot GPUs for heavy jobs.
3. **Review councils.** The fine-tune loop. Every project artifact gets
   critiqued by N different models in parallel on a schedule; only changes
   that 2+ critics agree on get merged (plus the single highest-leverage solo
   fix). Sayed's draft approval is the final, non-negotiable council seat.

---

## The virtual office map

- **This repo** = the source of truth. Every project file, crew definition,
  council config, and run log lives here with full history. Sayed can open it
  on his phone and see everything.
- **Compute, in phases:**
  - Phase 1 (now): the persistent workspace — subagents + scheduled crons. $0, zero new signups.
  - Phase 2: GitHub Actions free tier runs the crews as scheduled flows; models via OpenRouter (free tiers = $0). Keys live in GitHub Secrets, pasted by Sayed himself.
  - Phase 3: ~$5/mo VPS or Ollama on Sayed's home PC for unlimited local compute.
- **HQ dashboard** (`hq/dashboard.md`): the office window. Every project with a
  status dot, every crew's last/next run, latest council verdicts, and —
  most importantly — **Sayed's action queue**: the only things needing his hands.
- **GroupMe groups**: each crew reports to its own group (push). Main chat stays clean.

---

## Projects

| Project | Folder | Notes |
|---|---|---|
| Fox-ranger NFT launch | `projects/nft-launch/` | Lazy minting on Rarible ($0), milestones Oct 7–10 |
| SHiPTrOLLYARD brand | `projects/shiptrollyard/` | Print-on-demand clothing; TikTok/IG/Fourthwall |
| Beast Sports Network | `projects/beast-sports-network/` | AI commentary, original characters, federation-verified facts, zero game footage |
| AI video lab | `projects/ai-video-lab/` | Open-source video-model scouting, sample videos |
| Dropshipping research | `projects/dropshipping/` | Authorized programs + no-IP-risk product research |
| Highlander key | `projects/highlander-key/` | iPhone-as-key investigation (existing research linked, not duplicated) |
| Jacson's school watch | `projects/jacson-school/` | Cross-country + band updates from ParentSquare |
| Soccer teams | `projects/soccer-teams/` | Keller Thunder (U15) + Keller Phoenix (U9) schedules, headcounts |

Large binaries (art, video) stay out of git — manifests and scripts live here,
the files themselves live in the workspace / external storage.

---

## Crews (active)

Defined in `crews/`. Each file declares: schedule, goal, steps, report target,
and what needs Sayed's hands.

| Crew | Schedule | Reports to |
|---|---|---|
| `nft-launch.yaml` | every 5h | GroupMe "NFT Launch HQ" |
| `shiptrollyard.yaml` | every 5h | GroupMe "SHiPTrOLLYARD HQ" |
| `ai-video-scout.yaml` | every 4h | GroupMe "AI Video Lab" |
| `jacson-watch.yaml` | daily | main chat (standing request) |

Future crews (start only on Sayed's explicit word each): beast-sports-network,
dropshipping.

---

## The agency brain (provider-agnostic core)

- **`brain/sayeds-agency-brain.md`** — what the agency IS: projects, rules,
  costs, standing context. Provider-agnostic; this is what ChatGPT (primary)
  reads.
- **`brain/worker-config-muse.md`** — how Muse (secondary) executes it.
  Replaceable per worker.
- **`crews/*/SPEC.md`** — portable 10-point crew specs. Any worker (Muse, an
  OpenRouter model worker, a GitHub Action) inherits a crew by implementing
  its spec. The agency is the specs; workers are interchangeable.
- **`registry/models.yaml`** — the living model/tool pool, maintained daily
  by the AI Ecosystem Scout. Free-first, never hard-coded.
- **`router/`** — LiteLLM config + routing policy: best model for the job,
  paid routes gated behind Sayed's explicit approval.
- **`automations/ai-ecosystem-scout/`** — the daily scout that keeps the
  registry current and recommends architecture changes.

## Standing rules for every crew

1. **Draft before send.** Anything posted or messaged in Sayed's name —
   GroupMe messages, DMs, listings, uploads — goes out ONLY after he approves
   the wording. Draft first, send on his green light. No exceptions.
2. **Crews run on their own judgment** and surface ONLY: money/spending,
   legal/tax/banking submissions, passwords/credentials, deletions, and
   anything physically needing his hands (wallet signing, phone taps).
3. **Main chat stays clean.** Project reporting goes to each project's own
   GroupMe group, never the main chat. (Exception: jacson-watch reports to
   main chat per his standing request.)
4. **Verify before asserting.** Tag claims verified vs inherited. For sports
   content: confirm scores FIRST at the federation's official site (UEFA.com,
   FIFA, …), Google's sports panel as cross-check. Data feeds alone are not trusted.
5. **Label AI content** on all platforms (purely AI-generated characters have no
   US copyright protection — speed and audience are the moat).
6. **Secrets hygiene.** API keys and credentials live in `.env` / GitHub
   Secrets, pasted by Sayed himself. Never in chat, files, or git. (Same rule
   as his Yahoo app passwords: transient use, never stored.)
7. **No surprise new mouths.** New crews, new spending, new accounts — only on
   his explicit word.

---

## Deploying / going live

Phase 1 is already running (workspace crons). To take the office live:

1. Sayed creates the empty `sayeds-agency` repo on GitHub (account `ssdarwich2026-pixel`).
2. Push this repo: `git remote add origin …` / `git push -u origin main` (exact commands in the handoff note).
3. Sayed's three taps for the GroupMe bot (`integrations/groupme-bot/README.md`): create the bot at dev.groupme.com → host the server → set the callback URL.
4. Phase 2, when ready: OpenRouter key into GitHub Secrets → Actions workflows run the crews.

Background: the full plan lives in the deployment blueprint
(`../research/top100-ai-systems/agency-deployment-blueprint.md` in the
workspace; to be linked here once the repo is the home), and the top-100
systems research behind the stack choices sits beside it.
