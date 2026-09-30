#!/usr/bin/env bash
# One-liner installer for dovera.
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
echo "  dovera check <pdf-or-folder>   # check document(s) against a checklist"
echo "  dovera checklists              # list available checklists"
echo "  dovera ui                      # web UI (http://localhost:8600)"
echo "  dovera store                   # GraphQL store (http://localhost:8700)"
echo
echo "Backend: set ANTHROPIC_AUTH_TOKEN (or OPENAI_API_KEY), or use a local"
echo "model via Ollama: ollama serve && ollama pull qwen3:14b, then"
echo "  dovera check doc.pdf --backend ollama"
echo "Scanned PDFs need OCR: brew install tesseract tesseract-lang"
