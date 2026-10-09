# Foxwatch Operating Manual (portable)

For: ChatGPT or any successor agent continuing Foxwatch NFT work if Muse access lapses.
Owner/decider: Sayed Darwichzada. Budget: **$0 unless he explicitly approves spending.**
Nothing publishes or messages in his name without his approval of exact wording.
Never request or handle seed phrases / private keys. Signing is always manual, in his wallet.

## 1. What lives where (this package)

```
foxwatch-handoff/
├── README.md                  ← start here; resume checklist
├── OPERATING-MANUAL.md        ← this file
├── agency-brain/              ← sayeds-agency-brain.md + worker-config-muse.md
├── metadata/                  ← master JSON (54 records) + part-1..5.json
├── artwork/                   ← 53 listable PNGs, numbered FW-001..FW-053
├── scripts/foxwatch_pipeline.py← the reusable pipeline (stdlib + PIL only)
├── catalog/                   ← listing-manifest.csv + validation-report.md
├── test-batch/                ← the 10 Sayed APPROVED (2026-10-10): manifest excerpt + notes
├── promo/promo-templates.md   ← reusable post drafts + weekly content plan
└── reports/                   ← launch-plan.md, roadmap-to-5000.md, earlier validation report
```

Canonical source of truth (if reachable): `~/workspace/your_files/nft-launch/`.

## 2. The pipeline (the core reusable asset)

**Script:** `scripts/foxwatch_pipeline.py` — pure Python, no network, no wallet, no cost.

```bash
python3 scripts/foxwatch_pipeline.py \
  --art-dir ./artwork \
  --metadata ./metadata/foxwatch-batch2-metadata.json \
  --out-dir ./catalog \
  --exclude <comma-separated skip filenames>
```

**What it does:** matches PNGs↔metadata by filename · validates unique names/files,
required fields, well-formed traits, sane tiers · detects exact duplicates (sha256)
and near-duplicates (perceptual dHash; tune with `--dhash-threshold`, default 5) ·
writes `listing-manifest.csv` + `validation-report.md`. **It never invents missing
metadata** — gaps are reported as errors. Exit 0 = manifest written; exit 1 = blocking errors.

**Conventions:** catalog IDs are deterministic — premium tier first, then alphabetical
(`FW-001..FW-009` = the 9 premiums, `FW-010..FW-053` = standards). Excluded files get
`SKIP-nn`. Pricing flags (`--price-standard 0.005 --price-premium 0.01 --supply 100
--royalty 10`) are PROPOSED values applied only where a record lacks its own — they are
planning inputs until Sayed approves per batch.

**Known behavior:** this art family shares backgrounds, so dHash flags many
"near-duplicates" — these are review warnings, not errors. The one `SKIP-01` is the
out-of-focus piece Sayed excluded; it stays excluded unless he says otherwise.

## 3. Adding new artwork (batch workflow)

1. Drop new PNGs into `artwork/` (512×512 PNG).
2. Append records to `metadata/foxwatch-batch2-metadata.json` — required keys:
   `file` (exact filename), `name` (unique), `description`, `traits` (list of
   `{trait_type, value}`), `price_tier` (`standard`|`premium`). No invented text —
   every field must be written from actually viewing the art.
3. Run the pipeline. Fix all **errors**; visually review **warnings**.
4. If new art derives from the 45 templates: run duplicate detection against the
   full set (the pipeline does this automatically) and keep only genuinely new pieces.
5. Present the batch manifest to Sayed for approval (exact pieces + prices).
6. Only after approval: he performs the signing session (section 4). Then verify (section 5).

**The 45 reusable templates:** referenced in planning but NOT yet delivered to the
execution side as of 2026-10-10. When they arrive, store under `templates/` and follow
steps 1–4 above; do not list template files themselves.

## 4. Listing on Rarible (Sayed does this, on his phone)

Per artwork (~2–3 min): Create → **Ethereum** → **Multiple** → upload PNG →
price + 30-day expiry → collection **Rarible** (shared — never a custom collection,
which costs money) → **lazy-minting ON** → name + description → traits →
**10% royalty** → **100 copies** → review → **sign**.

**Signature safety rules (non-negotiable):**
- The MetaMask prompt must be a *signature/message request*, never a transaction with gas. Gas shown → STOP, do not approve, report it.
- One signature per listing — this is genuinely required; no safe batch-signing exists at $0.
- Use his dedicated NFT account. Never sign `setApprovalForAll` or unfamiliar contracts.
- Rarible's official docs confirm: lazy minting is $0 to the creator (buyer pays gas at purchase), ~2.5% marketplace fee only on sale, royalties settable up to 50%.
- **Reversal costs (verified 2026-10-10):** burning costs gas; Hide is free but
  display-only; cancelling a *bid* costs gas. Cancelling a *listing's* gas cost is
  UNVERIFIED — treat signing the listing as the commitment point and verify every
  field before signing. Never burn to "undo."
- **Bulk listing:** Rarible has NO supported bulk upload for distinct artworks (their help center says the feature is still "being worked on"). Do NOT build an API integration to work around this — unsupported, adds trust surface, saves nothing since signatures stay manual.

## 5. Verification after he lists (Gate 2)

For each listing, check against `catalog/listing-manifest.csv`: correct artwork,
name, description, traits, price, 30-day expiry, 100 supply, Rarible shared collection,
10% royalty, correct wallet/account, no unexpected charges or approvals. Any
difference → stop and report to Sayed before continuing the batch.

## 6. Weekly batch cadence (Phase 2: the remaining 43)

- **Mon:** select next ~11, run pipeline, QC + duplicate review.
- **Tue:** finalize metadata; stage batch manifest.
- **Wed:** Sayed approves exact pieces + prices.
- **Thu:** his signing session (~30 min).
- **Fri:** verify listings (section 5); publish approved promo (section 7).

Scale rule: new variations (Phase 3) only after sales data justifies production.
Listings ≠ sales — demand is the binding constraint, not supply.

## 7. Promotion (drafts only — never publish without his exact-wording approval)

Reusable templates + 4-week content plan: `promo/promo-templates.md`.
Funnel to track: content views → profile visits → Rarible page views → sales.

## 8. Resume checklist (first run after handoff)

1. Read `README.md` in this package.
2. Run the pipeline (section 2) to confirm it reproduces `catalog/` cleanly.
3. Check `test-batch/` — the 10 approved pieces and whether they were listed.
4. If unlisted: bring Sayed the approval → signing → verification loop (sections 4–5).
5. If listed: run Gate 2 verification, then continue the weekly cadence (section 6).
