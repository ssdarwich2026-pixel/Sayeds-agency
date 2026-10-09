# Foxwatch Bulk Launch — Launch Plan (Rarible)
Date: 2026-10-10 JST. Platform verified against Rarible official docs (help.rarible.com).

## Why Rarible
- **$0 upfront, verified:** lazy minting creates "ERC-721 & ERC-1155 NFTs for free (zero gas fee cost)" — buyer pays gas at purchase.
- **Editions, verified:** create flow offers "Single or Multiple" — Multiple lets you "enter how many copies of the item you wish to create."
- **Royalties:** up to 50% settable; we use 10%.
- **Constraints (verified):** lazy minting only on **Ethereum**, only into **Rarible's shared collection** (custom collection costs gas — do NOT create one).
- **Marketplace fee:** ~2.5% on sale (deducted from proceeds, not upfront).
- **No bulk distinct-artwork upload exists** in Rarible's UI. Each artwork = one "Create item" flow = one wallet signature. Editions multiply tokens per signature, not artworks per signature. (Programmatic minting via API exists but needs dev work + keys — out of scope for $0/no-code.)

## Why not OpenSea Studio
- Official FAQ: "you will need to pay gas fees to deploy your smart contract and mint the NFT." Contract deployment = guaranteed spend. Rejected under $0 rule.
- No native bulk distinct-artwork upload either; third-party "bulk upload" gigs are paid/sketchy — rejected per security rules.

## The model
- **53 designs** (9 premium + 44 standard), **100 editions each** = 5,300 max token supply.
- **53 signatures** total (one per design). Test batch first: 10 designs = 10 signatures.
- Pricing proposal: 0.005 ETH/edition standard (~$13), 0.01 ETH/edition premium (~$26). Sayed confirms.

## Exact steps per artwork (Sayed, on his phone)
1. rarible.com → Connect wallet (MetaMask, Account 4 = NFT account).
2. Create → NFT → blockchain **Ethereum**.
3. Choose **Multiple** (not Single).
4. Upload the PNG from the test-batch/main folder.
5. Price per edition + listing expiry (suggest 30 days, matching the Scout).
6. Collection: **Rarible** (shared) — do NOT create a custom collection.
7. **Free minting (lazy) toggle ON.**
8. Name + description: copy from manifest/metadata (exact text staged).
9. Show advanced settings → add traits as Properties.
10. Royalty: **10%**.
11. Copies: **100**.
12. Create item → **sign in MetaMask** (signature only, no gas).
13. Repeat per artwork. ~2–3 min each → test batch ≈ 25 min.

## What each signature authorizes
- A lazy-mint voucher: permission for Rarible to mint that artwork (up to 100 copies) to buyers on purchase. **No funds move.** Reversible by delisting (delisting a never-sold lazy item is free; burning after a sale would cost gas — don't burn).

## Rollback
- Before any sale: delist from Rarible profile (free).
- Nothing is on-chain until a buyer purchases — unsold items cost nothing and leave no chain footprint.

## Scale-up roadmap (designs listed, not tokens)
- **Phase 0 (now):** 10-design test batch → verify display, traits, pricing, purchase flow.
- **Phase 1:** remaining 43 designs in ~4 weekly batches (~11/week) — each batch is a mini marketing moment.
- **Phase 2 (optional):** the 300-fox pipeline (crew-built) feeds future weekly drops.
- Token supply scales via editions (100/design); design count scales via weekly batches. Never list duplicate 1/1s as a shortcut.
