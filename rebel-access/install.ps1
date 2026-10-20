# install.ps1 — One-click remote access setup for Sayed's PC
# Gives Muse (Agent 81) key-only SSH access over Sayed's private Tailscale network.
# NO public internet exposure: SSH is firewalled to the Tailscale address range only,
# password sign-in over SSH is disabled, and the only accepted credential is Muse's public key.

$ErrorActionPreference = 'Stop'

# --- Self-elevate to Administrator ---
$me = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $me.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Start-Process powershell -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    exit
}

$folder = if ($PSScriptRoot) { $PSScriptRoot } else { "$env:USERPROFILE\Desktop\RebelAccess" }
$log = Join-Path $folder 'install-result.txt'
function Note($m) { $m | Tee-Object -FilePath $log -Append }
"Remote access install — $(Get-Date)" | Set-Content $log

# --- 1. Tailscale (private network) ---
$ts = "$env:ProgramFiles\Tailscale\tailscale.exe"
if (-not (Test-Path $ts)) {
    Note 'Installing Tailscale...'
    winget install --id Tailscale.Tailscale -e --accept-source-agreements --accept-package-agreements
}
Note 'Opening Tailscale sign-in in your browser — sign in / create the free account, then return here.'
& $ts up
$tsip = (& $ts ip -4 | Select-Object -First 1)
Note "This PC's Tailscale IP: $tsip"

# --- 2. Windows OpenSSH Server ---
Note 'Installing and starting OpenSSH Server...'
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0 | Out-Null
Start-Service sshd
Set-Service sshd -StartupType Automatic

# --- 3. Muse's public key (public key only — safe to share; the private key never leaves Muse) ---
$pubkey = 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAHdYuQuQs0xo8O0pxxO2WAZrc6cWBuDiUkxW/7jhUJd hatch'
$adminKeys = "$env:ProgramData\ssh\administrators_authorized_keys"
if (-not (Test-Path $adminKeys) -or -not (Select-String -Path $adminKeys -SimpleMatch $pubkey -Quiet)) {
    Add-Content -Path $adminKeys -Value $pubkey
}
icacls $adminKeys /inheritance:r /grant 'Administrators:F' /grant 'SYSTEM:F' | Out-Null
Note 'Muse public key installed.'

# --- 4. Key-only SSH (no passwords) ---
$cfg = "$env:ProgramData\ssh\sshd_config"
Copy-Item $cfg "$cfg.bak" -Force
if (-not (Select-String -Path $cfg -Pattern '^PasswordAuthentication' -Quiet)) {
    Add-Content -Path $cfg -Value "`nPasswordAuthentication no`nPubkeyAuthentication yes"
}
Restart-Service sshd
Note 'SSH set to key-only sign-in.'

# --- 5. Firewall: SSH reachable ONLY from the Tailscale network (100.64.0.0/10) ---
Disable-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' -ErrorAction SilentlyContinue
if (-not (Get-NetFirewallRule -Name 'RebelAccess-SSH' -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -Name 'RebelAccess-SSH' -DisplayName 'SSH (Rebel Access - Tailscale only)' `
        -Direction Inbound -Protocol TCP -LocalPort 22 -RemoteAddress 100.64.0.0/10 -Action Allow | Out-Null
}
Note 'Firewall: SSH allowed from your Tailscale network only.'

# --- 6. Desktop shortcuts (Pitch Browser / Assess / Remove are each one click from now on) ---
Note 'Creating Desktop shortcuts...'
$ws = New-Object -ComObject WScript.Shell
function Make-Shortcut($name, $script) {
    $lnk = $ws.CreateShortcut("$env:USERPROFILE\Desktop\$name.lnk")
    $lnk.TargetPath = 'powershell.exe'
    $lnk.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$folder\$script`""
    $lnk.WorkingDirectory = $folder
    $lnk.Save()
}
Make-Shortcut 'Pitch Browser' 'start-pitch-browser.ps1'
Make-Shortcut 'Assess My PC' 'assess.ps1'
Make-Shortcut 'Remove Rebel Access' 'uninstall.ps1'
Note 'Shortcuts created: Pitch Browser, Assess My PC, Remove Rebel Access.'

# --- 7. Run the first read-only assessment right now and open the report ---
Note 'Running the first PC assessment (read-only)...'
& (Join-Path $folder 'assess.ps1')
$reportFile = "$env:USERPROFILE\Desktop\pc-inventory-report.md"
if (Test-Path $reportFile) { Invoke-Item $reportFile }
Note 'Assessment report opened: pc-inventory-report.md on the Desktop.'

Note ''
Note '================ DONE ================'
Note "Computer name : $env:COMPUTERNAME"
Note "Windows user  : $env:USERNAME"
Note "Tailscale IP  : $tsip"
Note 'Tell Muse: "install done" plus the Computer name and Tailscale IP above.'
Read-Host 'Press Enter to close'
