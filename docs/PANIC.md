# PANIC — lockdown runbook

If malicious code got in, a sleeper woke up, or the site is under attack:
do these in order. Each step is one click or one command.

## The four turns of the key

1. **Lock the doors.** Repo → Settings → Moderation → limit interactions
   to existing collaborators (or flip the repo private). Strangers can no
   longer open PRs or issues.
2. **Kill the public site.** Settings → Pages → "Unpublish site".
   The storefront goes dark instantly.
3. **Revert the bad change.** Find the commit → `git revert <sha>` →
   push. (Or via web: commit history → Revert.)
4. **Verify clean.** Open an issue titled `verify agency`, wait for the
   bot's PASS comment. Then write up what happened in the lockdown issue
   and unlock when clean.

## The big red button

Actions → `panic-button` → Run workflow. It opens a LOCKDOWN issue with
this runbook so nothing gets forgotten in the adrenaline.

Honest note: the button raises the alarm — a human turns the keys.
GitHub doesn't let a workflow lock the repo by itself, and that's fine:
four deliberate turns beat one accidental one.

## Why this works even if we lose

Everything is git. Every version of everything is recoverable in seconds
with `git revert` — nothing is ever truly burned down. And because it's
all MIT and forkable, the worst case ends with the community moving to a
clean fork and carrying on. The shop can burn; the blueprints can't.
