# Signing Interface Specification (manual signing — no automation)

Status: DOCUMENTATION ONLY. Signing stays manual in Sayed's wallet (his decision,
2026-10-10). No code in this project signs anything, holds keys, or connects a wallet.

## What a Rarible lazy-mint signature authorizes

When Sayed clicks "Create item" with lazy-minting ON, MetaMask shows a **signature
request** (EIP-712 typed message), not a transaction. That signature is a mint voucher:
it authorizes Rarible's marketplace contract to mint the token and transfer it to a
buyer **if and when** someone purchases at the listed terms. Nothing goes on-chain
until a purchase happens; the buyer pays the gas.

A signed voucher is NOT harmless-by-default: it can be submitted later within its
validity window, so every field below must be verified BEFORE signing.

## Voucher payload fields (what to verify per listing)

| Field | Must equal | Source of truth |
|---|---|---|
| Collection | Rarible shared collection (Ethereum) — never a custom collection | Rarible UI "Collection" selector |
| Token standard | ERC-1155 (Multiple) | "Multiple" selected |
| Artwork | the exact PNG for this catalog ID | `catalog/listing-manifest.csv` → filename + sha256 |
| Name / description / traits | the approved metadata | master metadata JSON |
| Price | approved price (0.005 standard / 0.01 premium unless re-approved) | manifest `price_eth` |
| Supply (editions) | 100 | manifest `supply` |
| Royalty | 10% to Sayed's wallet | manifest `royalty_pct` |
| Expiry | 30 days | listing form |
| Signing account | his dedicated NFT account (Account 4) | MetaMask account indicator |

## Pre-sign checklist (Sayed, per signature — ~10 seconds each)

1. Prompt type says **signature / sign message** — NOT "confirm transaction."
2. No gas fee shown. Gas shown → STOP, do not sign, report it.
3. Domain is rarible.com (check the domain line in the signature details).
4. Price, supply (100), royalty (10%), and artwork match the approved row.
5. Never sign `setApprovalForAll`, token spend approvals, or anything from an
   unfamiliar contract or site.

## Security checks the pipeline enforces BEFORE anything reaches signing

- `foxwatch_pipeline.py` validates: unique IDs/names/files, complete metadata,
  correct tiers, no byte-identical duplicates (sha256), near-duplicate review flags.
- The manifest is the single source of truth; Gate 2 verification re-checks every
  listed field against it after signing.
- Signing queue discipline: prepare all payloads → Sayed reviews the manifest →
  he signs per item → verify each listing. A mismatch at any step stops the batch.

## What would change for any future automated signer (NOT approved, NOT built)

Would require: a dedicated creator wallet (never the main wallet), narrowly scoped
permissions, explicit per-batch limits, secure key storage (HSM/KMS — not a cloud
bot's disk), a full signature audit log, and Sayed's explicit approval of the design.
Per his 2026-10-10 decision, this is out of scope until he asks for it.
