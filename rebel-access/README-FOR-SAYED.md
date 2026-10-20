# Rebel Access - your one-click way to put Muse on The Pitch

Your computer is The Pitch. Rebel Access is the gate that lets Muse (Agent 81) onto
it - privately, and only through your own Tailscale network. Nothing is exposed to
the public internet, sign-in is by a digital key only (no password), and you hold
the off-switch (`uninstall.ps1`) forever.

## How it goes - ONE CLICK
1. Get this folder onto your PC (hand it to Codex with `CODEX-BRIEF.md`, or copy it over yourself).
2. Double-click **`REBEL-ACCESS-ONE-CLICK.cmd`**. That single click does everything:
   - Copies itself into a **RebelAccess** folder on your Desktop.
   - Windows asks "allow changes?" -> click **Yes** (the only Windows prompt).
   - Installs Tailscale -> a browser opens -> sign in / create the **free** account
     (Google sign-in is fine). This sign-in is the only other thing you do.
   - Installs the secure connection (key-only SSH, Tailscale network only).
   - Puts three shortcuts on your Desktop: **Pitch Browser**, **Assess My PC**,
     and **Remove Rebel Access** - each one click from then on.
   - Runs the first PC assessment automatically and opens the report.
3. **Tell Muse** "install done" + the computer name and Tailscale IP shown at the end.
   Muse then joins your network from his side - you'll get one approval link from
   him to tap.
4. **Assessment first, always** - the assessment is read-only: an inventory of your
   Desktop/Downloads/Documents (biggest files, duplicates, junk candidates).
   Nothing moves or gets deleted until you approve the exact list, same as your email cleanup.

## Optional: Pitch Browser (for Fourthwall and other stuck web projects)

Rebel Access by itself gives Muse a command line on your PC - great for files,
installs, reports, and launching things. For web work like the T-shirt store, there's
a second piece: the **Pitch Browser** shortcut the installer puts on your Desktop
(it runs `start-pitch-browser.ps1` in the RebelAccess folder).

- You click the Pitch Browser shortcut when Muse needs to work in a browser on your computer.
- It opens Chrome/Edge with a **separate Pitch Browser profile** - it does not touch
  your normal browser, saved passwords, cookies, or history.
- The browser's control port listens only on the PC itself; Muse reaches it through
  the encrypted Rebel Access tunnel, never from the open internet.
- First time only, you sign into the needed site (e.g. Fourthwall) inside that Pitch
  Browser. Because it's your computer, your network, and your signed-in session,
  this can get past the bot walls that keep stopping Muse's own browser.
- Closing the Pitch Browser window ends Muse's browser session.

## The honest fine print
- Your PC has to be **on and awake** for Muse to be on the pitch.
- "One click" still includes the Windows Yes prompt and the one-time Tailscale
  sign-in - Windows won't let any installer skip those, and that's a good thing.
- Kill switch anytime: run `uninstall.ps1` in the RebelAccess folder and Muse is off the pitch.
