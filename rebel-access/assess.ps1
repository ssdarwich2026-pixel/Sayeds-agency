# assess.ps1 - READ-ONLY computer assessment for Sayed's PC.
# Inventories user folders and writes a report to the Desktop.
# This script NEVER moves, renames, or deletes anything.
$ErrorActionPreference = 'SilentlyContinue'
$report = "$env:USERPROFILE\Desktop\pc-inventory-report.md"
$names = 'Desktop','Downloads','Documents','Pictures','Videos','Music'
$folders = $names | ForEach-Object { Join-Path $env:USERPROFILE $_ } | Where-Object { Test-Path $_ }

$lines = @()
$lines += "# PC Inventory Report - $(Get-Date)"
$lines += ""
$all = @()
foreach ($f in $folders) {
    $files = Get-ChildItem $f -Recurse -File
    $all += $files
    $size = ($files | Measure-Object Length -Sum).Sum
    $lines += "## $f"
    $lines += "- Files: $($files.Count)  |  Size: $([math]::Round($size/1GB,2)) GB"
    $lines += ""
}
$lines += "## Biggest 50 files"
$all | Sort-Object Length -Descending | Select-Object -First 50 | ForEach-Object {
    $lines += "- $([math]::Round($_.Length/1MB,1)) MB - $($_.FullName)"
}
$lines += ""
$lines += "## Oldest 50 files in Downloads"
Get-ChildItem (Join-Path $env:USERPROFILE 'Downloads') -File | Sort-Object LastWriteTime | Select-Object -First 50 | ForEach-Object {
    $lines += "- $($_.LastWriteTime.ToString('yyyy-MM-dd')) - $($_.Name)"
}
$lines += ""
$lines += "## Likely duplicates (same name + same size)"
$all | Group-Object Name, Length | Where-Object { $_.Count -gt 1 } | Select-Object -First 100 | ForEach-Object {
    $lines += "- $($_.Name) x$($_.Count)"
}
$lines += ""
$lines += "## File types (all user folders)"
$all | Group-Object Extension | Sort-Object Count -Descending | Select-Object -First 25 | ForEach-Object {
    $lines += "- $($_.Name): $($_.Count)"
}
$lines | Set-Content $report
Write-Host "Report written to $report"
