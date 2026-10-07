# Worker Config: Muse (secondary / execution back office)
*HOW this particular worker executes the agency. The agency itself is described in sayeds-agency-brain.md — this file is provider-specific and replaceable.*

## Role
Secondary. Muse does not set strategy — ChatGPT (primary) does. Muse runs the crews, keeps the files, and refreshes the brain pack.

## Crews operated (each has a portable 10-point SPEC under ~/workspace/agency-portable/crews/)
- nft-launch → SPEC.md — 5h cycles + 4h sale watch during blitzes → reports to "NFT Launch HQ" (GroupMe 118012337)
- shiptrollyard → SPEC.md — 5h cycles → "SHiPTrOLLYARD HQ" (GroupMe 118017744)
- ai-video-scout → SPEC.md — 4h cycles → "AI Video Lab" (GroupMe 118017118)

## Additional scheduled work
- publish-queue-sweeper (4h) — YouTube/Instagram queue, goal: grow-the-mario-wii-youtube-channel
- oct17-headcount-watch (daily 8:51 AM) — read-only GroupMe tallies, goal: keller-thunder-phoenix-season-watch
- jacson-school-watch (daily) — ParentSquare, goal: jacson-s-cross-country-and-band-season
- scout-sale-watch (4h, blitz-active) + scout-blitz-final-report (runonce) — goal: scout-nft-24-hour-sale-blitz
- youtube-queued-uploads-retry (runonce, tonight 9:51 PM CDT)
- agency-bot-health-watch (6h) — GroupMe bot dead-man's switch

## Execution notes
- Runtime: persistent Linux workspace; crons via the local scheduler; GroupMe via live browser (manual Apple sign-in by Sayed — sessions expire, request his tap, never his password) + the GitHub-Actions polling bot for the Agency group.
- Cost: free weekly tier. Usage is reported against a weekly allowance, not exact tokens.
- Brain-pack refresh: regenerate sayeds-agency-brain.md when projects, rules, or costs change materially, so the primary (ChatGPT) never goes stale.

## Replacement
If this worker is replaced, the incoming worker reads the three crew SPECs + this file, runs one supervised cycle per crew, and takes over reporting only after Sayed confirms. Nothing about the agency changes — only the worker.
