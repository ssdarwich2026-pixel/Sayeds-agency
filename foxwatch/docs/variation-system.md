# Foxwatch Variation System v1

How new NFTs are "popped out" of the current collection — same style,
guaranteed unique. Any source (Muse, ChatGPT, contributors) follows the
same gate. No piece enters the collection without passing it.

## The loop

1. **Roster check.** Pick an occupation/archetype not already used.
   Roster: `docs/archetype-roster.md` (title + role + file). No repeats.
2. **Generate.** Image-to-image: one collection piece as style reference +
   prompt for the NEW archetype. Must follow `docs/style-bible.md`.
   Output: 512×512 PNG into `candidates/`.
3. **Uniqueness gate** (automatic, no exceptions):
   - SHA-256 vs every piece in `artwork/` and accepted candidates →
     reject if byte-identical.
   - dHash vs every piece → reject if hamming distance ≤ 5
     (the pipeline's near-duplicate threshold).
   - Gate script: run the pipeline with candidates in the art dir;
     any new error/warning naming the candidate = rejection.
4. **Metadata.** Name per style bible; description written from observing
   the art (never invented); core five traits + optionals from the schema.
5. **Human approval.** Sayed (or delegate) eyeballs the candidate.
   The gate catches copies; only a human catches "off-style".
6. **Promote.** Move PNG + metadata into `artwork/` and the master JSON,
   re-run the pipeline, confirm `errors=0`.

## Rejection handling

Rejected candidates are deleted or re-briefed, never force-fit.
If a brief keeps failing the gate, the archetype is too close to an
existing piece — pick a new one.

## Batch discipline

- Max 10 candidates per batch (keeps human review real).
- Every batch re-runs the full pipeline; the manifest is the source of truth.
- Prices/tiers are proposed until Sayed approves per batch.
