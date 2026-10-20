# CODEX BRIEF - "Rebel Access" (The Pitch)

Prepared by Muse (Agent 81) for Codex on Sayed's PC, 2026-10-20.
Sayed's name for it: **Rebel Access** - his computer is "The Pitch," and this package
is what puts Muse on the pitch with him.

## What you're building
A folder on Sayed's Desktop named **RebelAccess** containing a one-click installer
that gives Muse secure, private remote access to this PC so Muse can assess and
(when Sayed approves) organize his files - the same read-only-first doctrine as the
PC cleanup brief.

## The files (drafts are attached alongside this brief - use them as the base)
1. `REBEL-ACCESS-ONE-CLICK.cmd` - THE program, from Sayed's side: one double-click. It
   copies the package into Desktop\RebelAccess and runs install.ps1. Nothing else is
   launched by hand.
2. `install.ps1` - the master installer; after the access setup (below) it also creates
   Desktop shortcuts (Pitch Browser / Assess My PC / Remove Rebel Access) and runs the
   read-only assessment once, opening the report. It does, in order:
   - Installs Tailscale (winget) and runs `tailscale up` (browser sign-in is Sayed's - free account).
   - Installs + starts Windows OpenSSH Server, sets it to Automatic.
   - Installs Muse's PUBLIC key (verify it matches EXACTLY, character for character):
     `ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAHdYuQuQs0xo8O0pxxO2WAZrc6cWBuDiUkxW/7jhUJd hatch`
     into `C:\ProgramData\ssh\administrators_authorized_keys` with correct ACLs.
   - Backs up sshd_config, then sets key-only sign-in (`PasswordAuthentication no`).
   - Firewall: disables the default open SSH rule; adds rule `RebelAccess-SSH` allowing
     port 22 ONLY from the Tailscale range 100.64.0.0/10. No public-internet exposure.
   - Writes `install-result.txt` in the RebelAccess folder with computer name, Windows
     username, and the PC's Tailscale IPv4 - Sayed reads those two values to Muse.
3. `assess.ps1` - READ-ONLY inventory (never moves/deletes): per-folder file counts and
   sizes, 50 biggest files, 50 oldest Downloads, likely duplicates, file-type breakdown ->
   writes `pc-inventory-report.md` to the Desktop.
4. `uninstall.ps1` - removes Muse's key, disables SSH, removes the firewall rule,
   disconnects Tailscale. Full off-switch, always available to Sayed.
5. `start-pitch-browser.ps1` - OPTIONAL browser mode for projects blocked in Muse's
   own browser (e.g. the Fourthwall shirt launch). Sayed launches it manually. It opens
   Chrome/Edge with a dedicated PitchBrowserProfile under the RebelAccess folder and
   remote debugging bound to 127.0.0.1 only; Muse reaches it through the SSH tunnel.
   It must never point at Sayed's ordinary browser profile. Sayed performs any first-time
   site sign-ins in the Pitch Browser himself, and closing that browser ends the session.

## Your job, Codex
- Review the drafts; adapt anything machine-specific (Windows edition quirks - e.g. if
  `Add-WindowsCapability` name differs, resolve via `Get-WindowsCapability -Online | Where Name -like 'OpenSSH*'`).
- Create the `RebelAccess` folder on the Desktop with the final files.
- Do NOT run the installer yourself - Sayed launches it with the double-click so the
  UAC prompt and the Tailscale sign-in are his.
- Report back: final file list, anything you changed and why, and confirm the public
  key in your install.ps1 matches the one above exactly.

## Security rules (do not weaken)
- Key-only SSH; the key above is the ONLY credential added. Never add password auth,
  never open port 22 to the internet, never add any other key.
- No script in this package deletes or moves user files. assess.ps1 stays read-only.
