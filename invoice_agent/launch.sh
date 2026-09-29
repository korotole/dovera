#!/usr/bin/env bash
# Launch the Annex 13 checker UI (Streamlit) on port 8600.
# Usage: ./launch.sh [--port N] [--cli <pdf|folder>]
set -euo pipefail
cd "$(dirname "$0")/.."

PORT="8600"
if [[ "${1:-}" == "--port" ]]; then PORT="$2"; shift 2; fi

if [[ "${1:-}" == "--cli" ]]; then
  # headless CLI check: uv run python -m invoice_agent.main <pdf-or-folder> [--out report.md]
  shift
  exec uv run python -m invoice_agent.main "$@"
fi

mkdir -p /tmp/annex13_uploads
if lsof -i ":$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port $PORT already in use — app probably running: http://localhost:$PORT"
  exit 0
fi

echo "Starting Annex 13 checker on http://localhost:$PORT ..."
exec uv run streamlit run invoice_agent/app.py \
  --server.headless true --server.port "$PORT" --server.address 0.0.0.0
