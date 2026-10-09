# Foxwatch Handoff Package

**Purpose:** everything needed to keep producing and launching Foxwatch NFT batches
if Muse's service access lapses. Portable — hand this folder to ChatGPT or any agent.

**Status as of 2026-10-10:** 53 artworks validated, 10-item test batch APPROVED by Sayed
(staged, not yet listed — see `test-batch/approved-10.md`). No spending, no mints,
no listings, no signatures have occurred.

## Contents

- `OPERATING-MANUAL.md` — exact steps: pipeline, new-art batches, Rarible listing,
  signature safety, verification, weekly cadence, promo rules.
- `agency-brain/` — agency identity + worker config (planning/execution split).
- `metadata/` — master metadata JSON (54 records) + part files.
- `artwork/` — 53 listable PNGs (512×512).
- `scripts/foxwatch_pipeline.py` — reusable pipeline: match PNGs↔metadata, validate,
  duplicate-detect (sha256 + perceptual dHash), emit listing manifest. Stdlib + PIL only.
- `catalog/` — `listing-manifest.csv` (53 eligible) + `validation-report.md`.
- `test-batch/` — the approved 10: IDs, prices, filenames, exact listing steps.
- `promo/promo-templates.md` — reusable post drafts + 4-week content plan (drafts only).
- `reports/` — launch plan, 5,000-token roadmap, earlier validation report.

## Resume checklist (first run)

1. Read `OPERATING-MANUAL.md` sections 1–2 and 8.
2. Reproduce the catalog to prove the pipeline works:
   ```bash
   python3 scripts/foxwatch_pipeline.py --art-dir ./artwork \
     --metadata ./metadata/foxwatch-batch2-metadata.json \
     --out-dir /tmp/fw-check --exclude 1419648857_Looking_super_cool_for_my_haircut.png
   ```
   Expect: `records=54 eligible=53 errors=0`.
3. Check `test-batch/approved-10.md` — if unlisted, the next step is Sayed's manual
   listing + signing session, then Gate 2 verification (manual section 5).
4. Continue the weekly batch cadence (manual section 6) for the remaining 43.

## Key facts (verified, not assumed)

- Rarible lazy minting on Ethereum via Rarible's shared collection: $0 creator cost.
- One signature per listing, must be Sayed's — no safe automation exists.
- No supported bulk upload for distinct artworks (Rarible: feature still in development).
- ~2.5% marketplace fee only on sale; royalties settable to 10% (max 50%).
- 53 × 100 editions = 5,300 max supply at $0 — demand, not supply, is the constraint.
