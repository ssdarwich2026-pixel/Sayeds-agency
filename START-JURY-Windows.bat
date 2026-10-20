@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title Jury of Five Launcher

echo Starting the Jury of Five...
echo.

rem ---------- Load saved settings from .env in this folder ----------
rem (one KEY=VALUE per line; this is where your key and passcode live)
if exist ".env" (
    for /f "usebackq eol=# tokens=1* delims==" %%A in (".env") do (
        if not "%%A"=="" set "%%A=%%B"
    )
)

rem ---------- Find Python ----------
set "PYCMD="
py -3 --version >nul 2>&1
if not errorlevel 1 set "PYCMD=py -3"
if defined PYCMD goto :have_python
python --version >nul 2>&1
if not errorlevel 1 set "PYCMD=python"
if defined PYCMD goto :have_python

rem ---------- Not found: try installing it once with winget ----------
echo Python was not found. Trying to install it now (one-time, free)...
where winget >nul 2>&1
if errorlevel 1 goto :no_python
winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
py -3 --version >nul 2>&1
if not errorlevel 1 set "PYCMD=py -3"
if defined PYCMD goto :have_python
python --version >nul 2>&1
if not errorlevel 1 set "PYCMD=python"
if defined PYCMD goto :have_python
goto :no_python

:no_python
echo.
echo Python isn't installed yet - install it free from python.org,
echo tick "Add Python to PATH" during setup, then double-click this file again.
echo (If an installer just ran above, double-click this file once more first.)
echo.
pause
exit /b 1

:have_python

rem ---------- Make sure the one small add-on (pyyaml) is there ----------
%PYCMD% -c "import yaml" >nul 2>&1
if not errorlevel 1 goto :yaml_ok
echo Installing the one small add-on the Jury needs (pyyaml)...
%PYCMD% -m pip install --quiet pyyaml
:yaml_ok

rem ---------- First run only: ask for his OpenRouter key ----------
if defined OPENROUTER_API_KEY goto :key_ok
echo.
echo First run: the Jury needs your OpenRouter API key.
echo Get one free at openrouter.ai (Keys - Create Key, credit limit $0).
echo Paste it below and press Enter. It is saved ONLY on this computer,
echo in a file called .env in this folder - never sent anywhere else.
echo.
set /p "OPENROUTER_API_KEY=Your OpenRouter key: "
if not defined OPENROUTER_API_KEY goto :no_key
>>".env" echo OPENROUTER_API_KEY=%OPENROUTER_API_KEY%
echo Saved. You will not be asked again.
echo.
goto :key_ok

:no_key
echo.
echo No key was entered, so the Jury cannot start yet.
echo Double-click this file again when you have your key.
echo.
pause
exit /b 1

:key_ok

rem ---------- Which address the Jury opens on ----------
set "URLPORT=8765"
if defined JURY_APP_PORT set "URLPORT=%JURY_APP_PORT%"
if defined PORT set "URLPORT=%PORT%"

rem ---------- Start the Jury in its own window, open the browser ----------
start "Jury of Five" %PYCMD% council\app\server.py
timeout /t 3 /nobreak >nul
start "" "http://127.0.0.1:%URLPORT%"

echo.
echo The Jury is running: http://127.0.0.1:%URLPORT%
echo To stop it, close the "Jury of Five" window.
echo You can close THIS window now if you like.
echo.
pause
endlocal
