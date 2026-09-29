#!/usr/bin/env bash
# One-liner installer for the Annex 13 checker.
#
#   ./install.sh          # install + verify (creates .venv via uv)
#
# Requirements: Python 3.12+, uv (auto-installed if missing), tesseract
# (optional, for scanned PDFs: brew install tesseract tesseract-lang).
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v uv >/dev/null 2>&1; then
  echo "Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

uv sync
echo
echo "Installed. Try:"
echo "  uv run annex13 <pdf-or-folder>            # CLI check"
echo "  uv run annex13-ui                          # GUI (http://localhost:8600)"
echo "  uv run annex13-store                       # GraphQL store (http://localhost:8700)"
echo
echo "Env needed: ANTHROPIC_AUTH_TOKEN (or ANTHROPIC_API_KEY), optionally ANTHROPIC_BASE_URL."
echo "Scanned PDFs need OCR: brew install tesseract tesseract-lang"
