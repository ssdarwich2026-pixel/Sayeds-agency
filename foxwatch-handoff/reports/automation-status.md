# Automation Status Report — Foxwatch pipeline (2026-10-10)

## Ready and working today (verified)

- **Artwork vault + manifest:** 53 PNGs with permanent catalog IDs (`FW-001..FW-053`,
  premium-first alphabetical), sha256 recorded, in `catalog/listing-manifest.csv`.
- **Validator:** `scripts/foxwatch_pipeline.py` — matches PNGs↔metadata, validates
  fields/traits/tiers, byte + perceptual duplicate detection. 53 eligible, 0 errors.
- **Automated tests:** `scripts/test_pipeline.py` — 6 tests, all passing.
- **Reproducibility:** pipeline re-run from the handoff package yields a byte-identical
  manifest on any machine with Python 3 + PIL.
- **New-art ingestion:** documented batch workflow (drop PNGs → append metadata →
  run → review → approve). 45 templates not yet delivered; ingestion convention ready.
- **Promo drafts:** reusable templates + 4-week plan (`promo/promo-templates.md`).

## Requires Sayed's approval (his manual steps, cannot be delegated)

- Approving each batch's exact pieces + prices.
- The Rarible listing session: ~2–3 min/artwork, one signature per listing, on his
  phone, in his wallet. Estimated 25 min for the approved 10.
- Exact wording approval before anything publishes in his name.

## Cannot (or should not) be automated

- **Signing itself:** must come from his key; no supported path for a bot to sign
  without holding the private key. Per his decision: stays manual, per batch.
- **Bulk distinct-artwork upload:** Rarible has no supported bulk create flow
  (their help center: feature still in development). No API integration built —
  unsupported workarounds add trust surface without removing the signature bottleneck.
- **Reversal assumptions:** do not assume undoing a listing is free. Verified costs:
  burning costs gas (Rarible docs); hiding is free (display-only). Cancelling a
  *bid* costs gas (verified); cancelling a *listing's* cost is unverified — treat
  signing the listing as the commitment point.
- **Metadata authorship:** names/descriptions/traits must be written from viewing
  the art. The pipeline reports gaps; it never invents them.

## Net assessment

Everything before the wallet is automated and portable. Everything at and after the
wallet is Sayed's by design. The remaining manual cost is ~25 min per 10 listings —
that is the fixed cryptographic floor, not a tooling gap.
