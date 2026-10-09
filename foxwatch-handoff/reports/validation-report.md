# Foxwatch Bulk Launch — Validation Report
Date: 2026-10-10 JST. All checks run locally, $0 spent.

## Inventory
- **54 files** received from Sayed's Google Drive "Fox" folder (512×512 PNG, 16.1 MB total).
- **53 launchable.** 1 duplicate removed (byte-identical re-download artifact: `4250985850_Add_different_backgrounds_ 2.png`).
- **1 skipped:** `1419648857_Looking_super_cool_for_my_haircut.png` — rendered out of focus, unusable. Excluded from package, original preserved.

## Metadata (53/53 launchable)
- Every piece has: unique Foxwatch name, 1–2 sentence description, 4–6 traits, price tier.
- Tiers: **9 premium**, **44 standard**. No tier conflicts, no duplicate names (3 cross-batch dupes found and renamed).
- All 5 metadata workers **visually inspected** each image (filenames were misleading in several cases — e.g. "scoring_a_goal" files are calm portraits, "Eating_a_human" is an office fox; names reflect actual content).
- Traits use consistent types: Background, Outfit, Expression, Mood, Activity, Accessory, Companion.

## Image ↔ metadata matching
- manifest.csv maps `FW-001`–`FW-053` → artwork filename → original filename → tier → edition supply → price → batch.
- artwork/ contains 53 numbered PNGs, each a copy (originals untouched in `art/batch2/Fox/`).

## IP / originality
- All original fox-ranger characters. No real clubs, players, brands, or recognizable IP.
- Two soccer-adjacent pieces use generic balls/kits (The Captain, The Forward) — IP-safe.

## Existing listings (duplication check)
- The Scout (1/1, 0.05 ETH) is a **different artwork** (`piece-01-fox-scout.jpg`), not in batch 2. No overlap.
- The Warden is on hold per Sayed's sale-first directive — not in this package.

## Unresolved issues
- None blocking. Pricing (0.005 std / 0.01 premium ETH per edition) is a proposal — Sayed sets final numbers.
- Rarible trait import: properties are entered manually per listing ("Show advanced settings"); no manifest import exists — accounted for in launch-plan signing time.
