#!/bin/sh
# fix-github-push.sh - restore GitHub push access on the Muse VM (and any outlet
# where git runs as root but the deploy key lives in the hatch home).
#
# Root cause (hit 2026-10-07, 2026-10-18, 2026-10-20): git/ssh runs as root and
# looks in /root/.ssh, while the repo deploy key ("Muse", write access) lives
# canonically at /home/hatch/.ssh/id_ed25519 - the persistent home. Copying the
# key to /root works until the next VM deployment wipes /root/.ssh.
#
# Durable fix (this script): never copy the key. Point SSH config (both homes)
# and the repo's core.sshCommand at the canonical key path, then verify.
# Idempotent - safe to re-run after any deployment/restart.
set -eu

KEY="/home/hatch/.ssh/id_ed25519"
KH="/home/hatch/.ssh/known_hosts"

if [ ! -f "$KEY" ]; then
  echo "FAIL: canonical deploy key not found at $KEY" >&2
  echo "If the key itself is gone, a human must re-add a deploy key in GitHub repo Settings > Deploy keys." >&2
  exit 1
fi

for cfgdir in /home/hatch/.ssh /root/.ssh; do
  mkdir -p "$cfgdir"
  printf 'Host github.com\n  HostName github.com\n  User git\n  IdentityFile %s\n  IdentitiesOnly yes\n  UserKnownHostsFile %s\n' "$KEY" "$KH" > "$cfgdir/config"
  chmod 600 "$cfgdir/config"
done

# Run from inside the repo checkout:
git config core.sshCommand "ssh -i $KEY -o UserKnownHostsFile=$KH -o IdentitiesOnly=yes"

echo "Verifying (normal path, no env override)..."
git ls-remote origin HEAD
echo "OK: GitHub reachable with the canonical deploy key. Push with: git push origin HEAD:main HEAD:master"
