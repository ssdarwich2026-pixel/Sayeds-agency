#!/bin/bash
# Jury of Five (Model 2, standalone) - launcher for Linux.
# Run (or double-click, if your file manager offers "Run in Terminal"):
#   ./START-JURY-Linux.sh
# It starts the Jury in this terminal and opens it in your browser.
# To stop the Jury, press Ctrl+C here or close this terminal window.

cd "$(dirname "$0")" || exit 1

echo "Starting the Jury of Five..."
echo

# ---- Load saved settings from .env in this folder, if there is one ----
# (one KEY=VALUE per line; this is where your key and passcode live)
if [ -f .env ]; then
  while IFS='=' read -r _k _v; do
    case "$_k" in
      ''|'#'*) continue ;;
    esac
    if [[ "$_k" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
      export "$_k=$_v"
    fi
  done < .env
fi

# ---- Find Python 3 ----
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python isn't installed yet."
  echo
  echo "Install it free from:  https://www.python.org/downloads/"
  echo "(or with your package manager, e.g. sudo apt install python3 python3-pip)"
  echo "Then run this file again."
  echo
  printf "Press Enter to close... "
  read -r _x
  exit 1
fi
PY=python3

# ---- Make sure the one small add-on (pyyaml) is there ----
if ! $PY -c "import yaml" >/dev/null 2>&1; then
  echo "Installing the one small add-on the Jury needs (pyyaml)..."
  $PY -m pip install --user --quiet pyyaml 2>/dev/null \
    || $PY -m pip install --quiet pyyaml
fi

# ---- First run only: ask for his OpenRouter key and save it here ----
if [ -z "${OPENROUTER_API_KEY:-}" ]; then
  echo
  echo "First run: the Jury needs your OpenRouter API key."
  echo "Get one free at openrouter.ai (Keys -> Create Key, credit limit \$0)."
  echo "Paste it below and press Enter. It is saved ONLY on this computer,"
  echo "in a file called .env in this folder - never sent anywhere else."
  echo
  printf "Your OpenRouter key: "
  read -r OPENROUTER_API_KEY
  if [ -z "${OPENROUTER_API_KEY:-}" ]; then
    echo
    echo "No key was entered, so the Jury can't start yet."
    echo "Run this file again when you have your key."
    printf "Press Enter to close... "
    read -r _x
    exit 1
  fi
  export OPENROUTER_API_KEY
  printf "OPENROUTER_API_KEY=%s\n" "$OPENROUTER_API_KEY" >> .env
  chmod 600 .env 2>/dev/null
  echo "Saved. You won't be asked again."
  echo
fi

# ---- Which address the Jury opens on ----
URLPORT="${PORT:-${JURY_APP_PORT:-8765}}"

# ---- Start the Jury, then open it in the browser ----
$PY council/app/server.py &
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null' INT TERM

sleep 2
if command -v xdg-open >/dev/null 2>&1; then
  xdg-open "http://127.0.0.1:$URLPORT" >/dev/null 2>&1 &
fi

echo "The Jury is running:  http://127.0.0.1:$URLPORT"
echo "To stop it, press Ctrl+C here or close this terminal window."
wait $SERVER_PID
