# dovera

**dovera** verifies documents against checklists. It reads what a document
actually contains, compares it with what a checklist requires, reports
agreements and differences with verbatim evidence, and flags what needs a
human decision.

Ships with one checklist: **Annex 13** (Příloha č. 13) of Czech Decree
499/2006 Sb. — construction project documentation. Other document types
(invoices, contracts, permits…) are added by registering a new checklist —
nothing else changes.

## Principle

dovera **determines, it does not validate**. For every checklist item it
answers: what does the document contain, what does the checklist require,
do they agree, why do they differ (when establishable), what correction may
help, which decisions need human confirmation.

Hard rules, enforced in code (not in the prompt):

- every quoted evidence string must be found on the claimed page; unverifiable
  quotes downgrade the verdict to `uncertain` + human review
- quotes from a table of contents prove a headline exists, not the content —
  downgraded the same way
- unknown verdicts, hallucinated codes, skipped items → `uncertain`, never
  certainty
- section verdicts roll up deterministically from subsections; summary counts
  are recomputed, never taken from the model
- a document that is one volume of a bigger set is checked against its own
  scope (`not_applicable` for other volumes' items), not failed wholesale

## Install

```bash
./install.sh
```

Creates `.venv` via [uv](https://docs.astral.sh/uv/) (auto-installed).
Requires Python 3.12+. Optional, for scanned PDFs (OCR):

```bash
brew install tesseract tesseract-lang
```

Environment — pick one backend:

```bash
# Anthropic (default when key present)
export ANTHROPIC_AUTH_TOKEN=...      # or ANTHROPIC_API_KEY
export ANTHROPIC_BASE_URL=...        # optional gateway override

# OpenAI
export OPENAI_API_KEY=...
export OPENAI_BASE_URL=...           # optional gateway override

# Local models via Ollama (no key needed)
ollama serve && ollama pull qwen3:14b
```

Backend selection: `--backend anthropic|openai|ollama` (or `DOVERA_BACKEND`)
overrides; without it the first present key wins (Anthropic, OpenAI), else a
reachable local Ollama. Model overrides: `DOVERA_MODEL` or `--model`,
defaults `claude-sonnet-5` / `gpt-5.1` / `qwen3:14b`.

## Usage

### CLI

```bash
uv run dovera check doc.pdf                  # single document
uv run dovera check ./Beroun-Student/        # project folder (dossier mode)
uv run dovera check doc.pdf --out report.md --json-out results.json
uv run dovera check doc.pdf --checklist annex13
uv run dovera check doc.pdf --backend ollama  # local model (qwen3:14b)
uv run dovera checklists                     # list available checklists
```

Dossier mode checks every PDF/DOCX in the folder in parallel and merges the
verdicts into one result per requirement: strongest evidence wins with file
attribution, uncertainty anywhere without a `present` anywhere keeps the
item uncertain, a failing file never produces a false `missing`.

### Web UI (minimal)

```bash
uv run dovera ui            # http://localhost:8600
```

Upload a file, run the check, view the table, download Markdown/JSON.

### GraphQL store

Every run is persisted (JSON files under `/tmp/dovera_store`, override with
`DOVERA_STORE_DIR`). The GraphQL API serves them to other agents:

```bash
uv run dovera store         # http://localhost:8700/graphql
```

```graphql
query { checkRuns(docNameContains: "Beroun") {
  id docName checklist createdAt
  summary { present partial missing not_applicable uncertain }
  results { code verdict confidence evidence page evidenceVerified humanReview }
} }

mutation { saveCheckRun(doc: {
  docPath: "/projekty/Beroun/A_technicka_zprava.docx"
  summary: { present: 8 partial: 2 missing: 3 not_applicable: 7 uncertain: 2 }
  results: [{ code: "A.1.1" verdict: "present" evidence: "Název stavby: …" page: 1 }]
}) { id } }
```

A DB backend (Postgres, …) is a matter of implementing `CheckStore`
(three methods: `upsert`, `get`, `list`) and passing it to `Dovers(store=…)`.

### Python

```python
from dovera import Dovers
from dovera.models import build_model

dovers = Dovers(build_model())               # or any LangChain chat model
out = dovers.check("doc.pdf")                # or a folder path
for r in out["results"]:
    print(r["code"], r["verdict"], r["confidence"], r["evidence"][:80])
```

### Docker

```bash
docker build -t dovera .
docker run -p 8600:8600 -e ANTHROPIC_AUTH_TOKEN=... dovera        # UI
docker run -p 8700:8700 -e ANTHROPIC_AUTH_TOKEN=... dovera dovera store
docker run -e ANTHROPIC_AUTH_TOKEN=... dovera dovera check /docs  # CLI
# local model: point the container at the host's Ollama
docker run --add-host=host.docker.internal:host-gateway \
  -e DOVERA_BACKEND=ollama -e OLLAMA_HOST=http://host.docker.internal:11434 \
  dovera dovera check /docs
```

## Architecture

```
dovera/
├── checklists/          # what a document type must contain
│   ├── base.py          #   Requirement, Checklist, ChecklistRegistry
│   └── annex13.py       #   the Annex 13 checklist (one instance)
├── documents.py         # Document: PDF/DOCX loading, OCR fallback, TOC detection
├── models.py            # LLM backend factory: Anthropic / OpenAI / local Ollama
├── checking/
│   ├── results.py       # Verdict, Confidence, CheckResult, Summary
│   ├── agent.py         # ReAct checker agent (3 tools: requirements/search/read)
│   ├── prompt.py        # prompt template + checklist-specific rules
│   ├── verifier.py      # deterministic hardening: evidence checks, roll-up
│   ├── workflow.py      # single-document runner (size routing, timeouts)
│   └── dossier.py       # project runner (many files → merged verdicts)
├── pipeline.py          # Dovers facade — the one entry point
├── storage.py           # CheckStore ABC + JSON backend
├── server.py            # GraphQL API over the store
├── reporting.py         # Markdown/console rendering
└── cli.py               # dovera check|checklists|store|ui
```

Separation: the **checklist** says what must be there, the **document**
provides text, the **agent** proposes verdicts, the **verifier** disposes
(all truth guarantees live here), the **dossier** merges volumes, the
**store** persists, the **report** renders. Each layer knows only the
interfaces of the next — a new checklist touches exactly one file.

## Adding a checklist (customization)

A checklist is requirements + optional prompt rules. Create a file, e.g.
`dovera/checklists/invoices.py`:

```python
from dovera.checklists.base import Checklist, Requirement
from dovera.checklists import ChecklistRegistry

INVOICE_RULES = """- Dates and amounts must be consistent between summary
  and line items; a mismatch is "partial" with the mismatch described."""

class InvoiceChecklist(Checklist):
    title = "faktura_dokumentace"

    def __init__(self):
        super().__init__([
            Requirement("ID", "Identifikace", "IČO, DIČ, číslo faktury, datum",
                        keywords=("ičo", "dič", "faktura č")),
            Requirement("AMT", "Částky", "Celková částka, sazba DPH, položky",
                        keywords=("celková částka", "dph")),
            # …
        ])

ChecklistRegistry.register(InvoiceChecklist(), "invoices")
```

Or, without touching the package:

```python
from dovera.checklists import ChecklistRegistry
from dovera.checklists.base import Checklist, Requirement
from dovera.pipeline import Dovers

custom = Checklist([...])
ChecklistRegistry.register(custom, "mychecklist")
Dovers(model, checklist="mychecklist").check("doc.pdf")
```

Verdicts, evidence verification, roll-up, dossier merging, reports, UI and
the store all work unchanged — they only see the `Checklist` interface.

To make a checklist visible to the CLI permanently, register it inside
`dovera/checklists/__init__.py`.

## Development

```bash
uv sync --dev
uv run pytest tests/ -m "not e2e"    # unit tests (no LLM)
uv run pytest tests/ -m e2e          # LLM end-to-end (needs credentials)
```

E2E tests generate synthetic PDFs on first run (they are not committed).

## Roadmap

- per-project knowledgebase: attach a project profile (parties, expected
  volumes, known deviations) that the checklist prompts reference
- additional checklists beyond Annex 13
- DB-backed store implementations
