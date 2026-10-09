# Foxwatch Lab Benchmark 35 — programmer resource

Reproducible pipeline that future programmers extend to grow the collection.

## What this is
35 fox characters (7 each: chefs, alchemists, musicians, explorers, craftsmen),
generated from `prompt-spec.json`, gated by `pipeline/uniqueness_gate.py`.

## Files
- `prompt-spec.json` — the exact template + per-character prompts + style refs.
- `character-plan.json` — roster-checked names (no collisions with the 53).
- `manifest.csv` — filename, character, career, SHA-256, dHash (after run).
- `START_TIME` / `END_TIME` — UTC timestamps of the run.
- `bench-*.png` — the 35 images.

## Reproduce / extend
1. Pick new occupations; check against `docs/archetype-roster.md`.
2. Add entries to a new prompt-spec (same template, new descs).
3. Generate (any image model that takes a style-reference image).
4. Gate: `python3 ../pipeline/uniqueness_gate.py --new-dir <dir> --collection-dir ../artwork/`
   Exit 0 = all pass. Fix or drop failures, never force them through.
5. Append passing names to the roster; rebuild the manifest.

## Invariants
- Style: `docs/style-bible.md`. Gate: SHA-256 + dHash ≤ 5.
- Nothing here mints, lists, or signs. $0 always.
