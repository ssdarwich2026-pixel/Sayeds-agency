# Foxwatch — Contributor Brief (for your brother's Muse)

## What this is
Foxwatch is Sayed Darwichzada's NFT collection: 53 fox-character artworks, 100
editions each (5,300 max supply), listed on Rarible with lazy minting ($0 creator
cost). Goal: get everything online by Oct 15, 2026 and market it. Sayed owns the
project and approves everything.

## Get up to speed (read in order)
1. `foxwatch-complete-handoff.md` — the whole project in one file: status, manual,
   manifest, metadata, script sources.
2. `foxwatch-handoff.zip` — the full package (artwork, scripts, docs).

## Run the pipeline
```bash
python3 scripts/foxwatch_pipeline.py --art-dir ./artwork \
  --metadata ./metadata/foxwatch-batch2-metadata.json \
  --out-dir ./out --exclude 1419648857_Looking_super_cool_for_my_haircut.png
# expect: records=54 eligible=53 errors=0
python3 scripts/test_pipeline.py   # expect: 6 tests OK
```

## How we collaborate
- GitHub repo `ssdarwich2026-pixel/Sayeds-agency` is the shared source of truth
  (public; ask Sayed to add you as collaborator for push access).
- Work on a branch, keep `listing-manifest.csv` regenerable via the script —
  never hand-edit it. Metadata changes go in the JSON, then re-run.
- Suggested split: you take new artwork variations + marketing drafts; Sayed's
  side keeps the pipeline, listing verification, and wallet steps.

## Hard rules (no exceptions)
- NEVER ask for or handle Sayed's seed phrase or private keys.
- No wallet signatures, transactions, or spending — only Sayed signs, on his phone.
- Nothing publishes or messages in Sayed's name without his exact-wording approval.
- $0 spend unless Sayed explicitly approves.
- Sayed approves every batch's pieces + prices before anything is listed.
