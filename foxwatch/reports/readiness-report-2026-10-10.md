# Foxwatch Readiness Report — 2026-10-10 (evidence-based)

Verdict: **Code and catalog verified. Launch blocked only on human steps
(wallet signatures, exchange setup, marketing posts).**

No listing, publishing, signing, spending, or price changes were made in this pass.

## 1. Handoff ZIP contents (verified by inspection)

`foxwatch-handoff.zip` (rebuilt this pass) contains:
- `scripts/foxwatch_pipeline.py` — preparation pipeline (offline, no network/keys)
- `scripts/test_pipeline.py` — 6 automated tests
- `artwork/` — 53 PNGs, 512×512
- `metadata/foxwatch-batch2-metadata.json` — 54 records (53 listable + 1 skip-tier)
- `catalog/listing-manifest.csv` — full 53-item manifest
- `test-batch/approved-10.md` — the approved ten, artwork + prices
- `reports/signing-interface.md` — signing specification
- `listing-schedule-50k.csv` — 10 × 5,000 editions = 50,000
- `docs/listing-checklists-50k.md` — per-item phone checklists
- `docs/getting-paid.md` — exchange/bank setup guide
- `MISSION.md`, `OPERATING-MANUAL.md`, contributor brief, marketing drafts

## 2. Test suite — exact names, command, output

Command: `python3 test_pipeline.py -v` (in `scripts/`)

1. `TestNormRecord.test_accepts_both_key_styles` ... ok
2. `TestNormRecord.test_missing_fields_reported_not_invented` ... ok
3. `TestNormRecord.test_duplicate_trait_type_flagged` ... ok
4. `TestDuplicates.test_sha256_distinguishes_files` ... ok
5. `TestDuplicates.test_dhash_similar_vs_different` ... ok
6. `TestEndToEnd.test_full_run_two_artworks` ... ok

Result: `Ran 6 tests in 0.200s — OK` (6/6 pass).

## 3. Pipeline reproducibility — run twice, diffed

Command (both runs): `python3 foxwatch_pipeline.py --art-dir artwork/
--metadata metadata/foxwatch-batch2-metadata.json --out-dir /tmp/fw_runN`

- Run 1: `records=54 eligible=53 errors=0 warnings=29`
- Run 2: `records=54 eligible=53 errors=0 warnings=29`
- `diff` of `listing-manifest.csv`: **identical**
- `diff -r` of full output dirs (manifest + validation report): **identical**

Deterministic. The 29 warnings are review flags (28 perceptual-similarity
pairs + the excluded skip-tier record), not blocking errors.

## 4. Negative tests — 5/5 pass (temp dirs, originals untouched)

| Case | Expected | Observed |
|---|---|---|
| N1 byte-identical duplicate PNG | exit 1, "byte-identical duplicates" | PASS |
| N2 duplicate metadata names | exit 1, "duplicate name" | PASS |
| N3 metadata references missing PNG | exit 1, "missing on disk" | PASS |
| N4a malformed JSON metadata | non-zero exit, no silent pass | PASS |
| N4b record missing name/description | exit 1, reported — never invented | PASS |

Failures block with exit code 1 and details in `validation-report.md`.
Nothing mints, lists, or signs — the pipeline is offline preparation only.

## 5. 50,000-edition CSV — verified by computation

`listing-schedule-50k.csv`: 10 rows × 5,000 = **50,000 total. PASS.**
Prices: 9 premium × 0.005 ETH, 1 standard × 0.001 ETH — all match the
approved impulse-pricing decision. Royalty 10%, expiry 30 days on all rows.

## 6. Persistent backup — exact locations and versions

- **Local git repo:** `~/workspace/agency` — commit `f4e9fba`
  "Fix CI: move foxwatch workflow to repo-root .github/workflows
  with contents:write". Tracks `foxwatch/` (project) and `foxwatch-handoff/`.
  Working tree clean.
- **Handoff package:** `~/workspace/your_files/nft-launch/foxwatch-handoff/`
  (+ `foxwatch-handoff.zip`, rebuilt this pass).
- **GitHub:** `ssdarwich2026-pixel/Sayeds-agency` — **NOT pushed.**
  Push blocked: this VM's SSH key
  (SHA256:phoIefWIGhl/B7lVhTSVijHMyzh8RjXVbFq6CLax0dw) is not authorized
  as a deploy key. Until Sayed adds it, there is **no off-site backup
  of the code** — the VM disk is the only copy. Google Drive holds only
  the original 54 uploads, not the pipeline or docs.
- **CI fix (this pass):** workflow moved from
  `foxwatch/.github/workflows/` (invisible to GitHub) to repo-root
  `.github/workflows/` with `permissions: contents: write` for the daily
  report commit. **Not yet live** — takes effect on first push; no Actions
  run has been observed.

## 7. Verified vs NOT independently checked

**Verified this pass:** items 1–6 above (tests, determinism, negative
cases, CSV math, repo state, CI path fix).

**NOT independently checked — do not treat as confirmed:**
- Rarible's current creator UI (form fields, lazy-mint toggle, 2.5% fee,
  listing-cancel cost). The live pilot never reached the form.
- Whether Rarible "Multiple" accepts 5,000 copies per listing (no
  documented cap found; the UI is the source of truth).
- The 10 phone signatures (MetaMask mobile-browser path untested end to end).
- ETH price (~$2,500 on Oct 9 — moves; recheck at sale time).
- The Scout's current sale status (last checked Oct 8–9).
- Marketing drafts (written, **not approved, not posted**).
- The 45 reusable templates (referenced in planning, not received).
- ChatGPT's independent test pass (queued, not yet run).
- GitHub Actions actually executing (blocked on push).

## Human steps remaining (only Sayed)

1. 10 signatures via MetaMask mobile browser (~30 min, checklists in
   `docs/listing-checklists-50k.md`). No QR codes.
2. Coinbase + bank setup (`docs/getting-paid.md`).
3. Approve/post marketing wording.
4. Add the deploy key so the repo (and CI) goes live.
