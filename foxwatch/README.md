# Foxwatch

An open-source NFT production pipeline. 53 fox-character artworks, 100 editions
each (5,300 max supply), prepared for listing on Rarible with lazy minting.

Owner: Sayed Darwichzada. He approves every batch and signs every listing —
no bot in this project can sign, spend, or publish in his name.

## Status

- Catalog: 53/53 artworks validated, 0 errors (`catalog/listing-manifest.csv`)
- Tests: `python pipeline/test_pipeline.py` (6 tests)
- Daily validation runs via GitHub Actions; reports land in `reports/daily/`

## Quickstart

```bash
pip install pillow   # only dependency
python pipeline/test_pipeline.py
python pipeline/foxwatch_pipeline.py --art-dir ./artwork \
  --metadata ./metadata/foxwatch-batch2-metadata.json \
  --out-dir ./out --exclude 1419648857_Looking_super_cool_for_my_haircut.png
# expect: records=54 eligible=53 errors=0
```

## Layout

- `pipeline/` — validator + manifest generator (offline, no keys, no network)
- `metadata/` — master metadata JSON (descriptions/traits written from the art)
- `artwork/` — 53 PNGs (© Sayed Darwichzada, all rights reserved — not MIT)
- `catalog/` — generated listing manifest + per-day listing schedule
- `docs/` — operating manual, signing spec, roadmap, approved batches
- `promo/` — post templates + marketing calendar (drafts only)
- `reports/daily/` — automated validation reports

## License

Code, scripts, and docs: MIT (see LICENSE). Artwork in `artwork/`: all rights
reserved by Sayed Darwichzada.

## Contributing

See CONTRIBUTING.md. TL;DR: change metadata, re-run the pipeline, never hand-edit
the manifest. Sayed approves all batches, prices, and wording.
