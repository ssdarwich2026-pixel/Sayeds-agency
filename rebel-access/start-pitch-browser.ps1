# start-pitch-browser.ps1 - Sayed starts this when Muse needs to work in a browser on The Pitch.
#
# What it does:
# - Opens Chrome (or Edge if Chrome is absent) using a DEDICATED Rebel Access browser profile.
# - Enables browser remote debugging on 127.0.0.1 ONLY. It is not exposed to the local network
#   or the public internet. Muse reaches it only through the encrypted Rebel Access SSH tunnel.
# - The first time it opens, Sayed signs into the sites he wants Muse to use in that profile.
# - Closing the Pitch Browser window ends Muse's browser session.
#
# This does not use or expose Sayed's ordinary browser profile, saved passwords, cookies,
# or browsing history.

$ErrorActionPreference = 'Stop'
$profile = "$env:USERPROFILE\Desktop\RebelAccess\PitchBrowserProfile"
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

$args = "--remote-debugging-address=127.0.0.1 --remote-debugging-port=9222 --remote-allow-origins=* --user-data-dir=`"$profile`" --no-first-run https://www.google.com"
Start-Process -FilePath $browser -ArgumentList $args

Write-Host ""
Write-Host "Pitch Browser started in $browserName."
Write-Host "1. Sign into any site Sayed wants Muse to use in this special browser profile."
Write-Host "2. Tell Muse: 'Pitch Browser is open.'"
Write-Host "3. Close this browser window when the work is finished."
Write-Host ""
Read-Host 'Press Enter to close this launcher window (the browser stays open)'
