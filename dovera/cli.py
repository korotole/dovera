"""dovera CLI.

    dovera check <file|folder>   check document(s) against a checklist
    dovera checklists            list available checklists
    dovera store                 run the GraphQL result store
    dovera ui                    run the minimal web UI
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from dotenv import load_dotenv


def build_model(model_name: str | None, backend: str | None = None):
    from dovera.models import build_model as _build

    return _build(backend=backend, model=model_name)


def cmd_check(args) -> int:
    from dovera.pipeline import Dovers
    from dovera.reporting import print_console_summary, to_markdown

    load_dotenv()
    dovers = Dovers(build_model(args.model, args.backend), checklist=args.checklist)
    try:
        out = dovers.check(args.target)
    except Exception as exc:
        print(f"Check failed: {exc}", file=sys.stderr)
        return 1

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
    md = to_markdown(out)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(md)
    else:
        print(md)
    print_console_summary(out)
    return 0


def cmd_checklists(_) -> int:
    from dovera.checklists import ChecklistRegistry

    for name in ChecklistRegistry.names():
        cl = ChecklistRegistry.get(name)
        print(f"{name:20s} {len(cl):3d} requirements  {cl.title}")
    return 0


def cmd_store(args) -> int:
    from dovera.server import main as serve

    serve(port=args.port)
    return 0


def cmd_ui(args) -> int:
    import subprocess
    import sys

    from pathlib import Path

    app_path = Path(__file__).parent / "ui.py"
    sys.exit(subprocess.call([
        sys.executable, "-m", "streamlit", "run", str(app_path),
        "--server.headless", "true",
        "--server.port", str(args.port),
        "--server.address", "0.0.0.0",
    ]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="dovera",
        description="Universal document verification against project checklists")
    sub = parser.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser("check", help="check a document or folder")
    p_check.add_argument("target", help="PDF/DOCX file, or folder for dossier mode")
    p_check.add_argument("--checklist", default="annex13",
                         help="checklist name (see: dovera checklists)")
    p_check.add_argument("--backend", default=None,
                         help="anthropic | openai | ollama (default: auto by env)")
    p_check.add_argument("--model", default=None, help="model override")
    p_check.add_argument("--out", default=None, help="write Markdown report here")
    p_check.add_argument("--json-out", default=None, help="write raw JSON here")
    p_check.set_defaults(func=cmd_check)

    p_lists = sub.add_parser("checklists", help="list available checklists")
    p_lists.set_defaults(func=cmd_checklists)

    p_store = sub.add_parser("store", help="run GraphQL result store")
    p_store.add_argument("--port", type=int, default=8700)
    p_store.set_defaults(func=cmd_store)

    p_ui = sub.add_parser("ui", help="run minimal web UI")
    p_ui.add_argument("--port", type=int, default=8600)
    p_ui.set_defaults(func=cmd_ui)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
