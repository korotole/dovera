"""CLI entry point: check a PDF against Annex 13 of Decree 499/2006 Sb.

Usage:
    uv run python -m invoice_agent.main <pdf> [--model <name>] [--out report.md]
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from dotenv import load_dotenv


def build_model(model_name: str | None):
    from langchain_anthropic import ChatAnthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    base_url = os.environ.get("ANTHROPIC_BASE_URL")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN not set")

    return ChatAnthropic(
        model=model_name or os.environ.get("AGENT_MODEL", "claude-sonnet-5"),
        max_tokens=8000,
        timeout=300,
        api_key=api_key,
        base_url=base_url,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Annex 13 compliance checker")
    parser.add_argument("pdf", help="Path to the PDF/DOCX to check (a folder runs dossier mode over all PDF/DOCX files in it)")
    parser.add_argument("--model", default=None, help="Model name override")
    parser.add_argument("--out", default=None, help="Write Markdown report to file")
    parser.add_argument("--json-out", default=None, help="Write raw JSON verdict to file")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

    from pathlib import Path

    from .report import print_console_summary, to_markdown

    model = build_model(args.model)
    try:
        target = Path(args.pdf)
        if target.is_dir():
            from .dossier import run_dossier
            data = run_dossier(args.pdf, model, verbose=args.verbose)
        else:
            from .agent import check_document
            data = check_document(args.pdf, model, verbose=args.verbose)
    except Exception as exc:  # noqa: BLE001
        print(f"Check failed: {exc}", file=sys.stderr)
        return 1

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    md = to_markdown(data)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(md)
    else:
        print(md)

    print_console_summary(data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
