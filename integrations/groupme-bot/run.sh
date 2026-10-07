#!/usr/bin/env bash
# Start the GroupMe bot webhook server.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -f .env ]; then
  echo "ERROR: .env not found. Copy .env.example to .env and fill it in first."
  exit 1
fi

# Load .env (python-dotenv also does this; harmless to do both)
set -a
source .env
set +a

PORT="${PORT:-8000}"
echo "Starting GroupMe bot on port $PORT ..."
exec uvicorn server:app --host 0.0.0.0 --port "$PORT"
