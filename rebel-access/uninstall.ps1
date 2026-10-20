# uninstall.ps1 - Removes Muse's remote access from this PC.
# Run as Administrator. Removes the key, stops SSH, removes the firewall rule,
# and disconnects Tailscale. (Tailscale itself stays installed; remove it from
# Windows Settings > Apps if you want it gone too.)
$me = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $me.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Start-Process powershell -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    exit
}
$pubkeyPart = 'AAAAC3NzaC1lZDI1NTE5AAAAIAHdYuQuQs0xo8O0pxxO2WAZrc6cWBuDiUkxW/7jhUJd'
$adminKeys = "$env:ProgramData\ssh\administrators_authorized_keys"
if (Test-Path $adminKeys) {
    (Get-Content $adminKeys) | Where-Object { $_ -notmatch [regex]::Escape($pubkeyPart) } | Set-Content $adminKeys
}
Stop-Service sshd -ErrorAction SilentlyContinue
Set-Service sshd -StartupType Disabled -ErrorAction SilentlyContinue
Remove-NetFirewallRule -Name 'RebelAccess-SSH' -ErrorAction SilentlyContinue
& "$env:ProgramFiles\Tailscale\tailscale.exe" down
Write-Host 'Remote access removed.'
Read-Host 'Press Enter to close'
