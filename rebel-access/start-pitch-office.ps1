# start-pitch-office.ps1 - Opens an additional Pitch Browser "office" on The Pitch.
#
# Each office is a fully separate Chrome instance:
# - Its own profile folder (own logins, cookies, sessions - offices never share state)
# - Its own remote-debugging port on 127.0.0.1 only (reachable by Muse only via Rebel Access SSH)
# - Its own renderer limit so several offices can idle side by side at low "RPM"
#   instead of one browser eating the whole machine.
#
# Office map:
#   Office 1 = the original Pitch Browser (start-pitch-browser.ps1, port 9222)
#   Office 2 = port 9223, profile PitchOffice2Profile
#   Office 3 = port 9224, profile PitchOffice3Profile
#   Office 4 = port 9225, profile PitchOffice4Profile
#
# Usage: powershell -File start-pitch-office.ps1 -Office 2

param(
    [Parameter(Mandatory = $true)]
    [ValidateRange(2, 4)]
    [int]$Office
)

$ErrorActionPreference = 'Stop'
$port = 9221 + $Office
$profile = "$env:USERPROFILE\Desktop\RebelAccess\PitchOffice$Office`Profile"
New-Item -ItemType Directory -Force -Path $profile | Out-Null

$chromeCandidates = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LocalAppData\Google\Chrome\Application\chrome.exe"
)
$edgeCandidates = @(
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe"
)

$browser = $chromeCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
$browserName = 'Chrome'
if (-not $browser) {
    $browser = $edgeCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    $browserName = 'Edge'
}
if (-not $browser) {
    throw 'Chrome or Edge was not found. Install Chrome, then run this again.'
}

# Throttle flags: cap renderers and cache so offices cruise at low RPM.
$args = "--remote-debugging-address=127.0.0.1 --remote-debugging-port=$port --remote-allow-origins=* --user-data-dir=`"$profile`" --no-first-run --renderer-process-limit=4 --disk-cache-size=268435456 --window-name=`"Pitch Office $Office`" https://www.google.com"
$proc = Start-Process -FilePath $browser -ArgumentList $args -PassThru

# Run this office at BelowNormal priority so it never fights Sayed's own work.
try { $proc.PriorityClass = 'BelowNormal' } catch { }

Write-Host ""
Write-Host "Pitch Office $Office started in $browserName on port $port."
Write-Host "1. Sign into any site for THIS office only (offices do not share logins)."
Write-Host "2. Close this browser window when the office's work is finished."
Write-Host ""
Read-Host 'Press Enter to close this launcher window (the browser stays open)'
