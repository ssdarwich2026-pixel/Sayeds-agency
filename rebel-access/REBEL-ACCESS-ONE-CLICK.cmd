@echo off
REM ============================================================
REM  REBEL ACCESS - THE ONE CLICK
REM  Double-click this file. Then: click YES on the Windows
REM  prompt, sign into free Tailscale in the browser that
REM  opens, and you're done. Everything else is automatic.
REM ============================================================
set DEST=%USERPROFILE%\Desktop\RebelAccess
if not exist "%DEST%" mkdir "%DEST%"
copy /Y "%~dp0*.ps1" "%DEST%\" >nul
copy /Y "%~dp0*.md" "%DEST%\" >nul
copy /Y "%~dp0REBEL-ACCESS-ONE-CLICK.cmd" "%DEST%\" >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%DEST%\install.ps1"
pause
