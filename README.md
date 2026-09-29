# Annex 13 Checker — Kontrola projektové dokumentace

LangGraph + LangChain agent checks construction project-documentation files
(PDF incl. scanned → OCR, DOCX) against **Annex 13 (Příloha č. 13) of Czech
Decree 499/2006 Sb.** Results are stored in a GraphQL store for reuse by
further agents.

## Principle

The agent **determines, it does not validate**. It reports what the document
contains, what the checklist requires, whether they agree, why they differ
(when establishable), what correction may help, and which items need human
confirmation. It never hides discrepancies, never converts uncertainty into
certainty, never invents information.

## Install (one-liner)

```bash
./install.sh
```

Creates `.venv` via [uv](https://docs.astral.sh/uv/) (auto-installed if
missing). Optional for scanned PDFs: `brew install tesseract tesseract-lang`.

Environment:

```bash
export ANTHROPIC_AUTH_TOKEN=...      # or ANTHROPIC_API_KEY
export ANTHROPIC_BASE_URL=...        # optional gateway override
```

## Usage

```bash
# CLI: check a PDF/DOCX, or a whole folder (dossier of volumes)
uv run annex13 documentation.pdf
uv run annex13 /path/to/project-folder/ --out report.md --json-out verdicts.json

# minimal GUI
uv run annex13-ui            # http://localhost:8600

# GraphQL result store
uv run annex13-store         # http://localhost:8700/graphql
```

### Docker

```bash
docker build -t annex13-checker .
docker run --rm -p 8600:8600 -e ANTHROPIC_AUTH_TOKEN=... annex13-checker                # GUI
docker run --rm -p 8700:8700 annex13-checker annex13-store                              # GraphQL
docker run --rm -e ANTHROPIC_AUTH_TOKEN=... -v "$PWD:/data" annex13-checker annex13 /data/doc.pdf
```

## GraphQL store

Every check run is persisted automatically (JSON files under
`ANNEX13_STORE_DIR`, default `/tmp/annex13_store`). Query it:

```graphql
mutation {
  saveCheckRun(doc: {
    docPath: "/docs/B_zprava.docx"
    summary: { present: 2, partial: 7, uncertain: 2 }
    results: [{ code: "B.1", verdict: "present", evidence: "…", page: 12 }]
  }) { id }
}

query {
  checkRuns(docNameContains: "zprava") {
    id docName updatedAt summary { present partial missing uncertain }
    results { code verdict confidence evidence evidenceVerified humanReview }
  }
}
```

Future agents read verdicts, evidence and file attribution from here instead
of re-running the LLM.

## Verdicts

`present` / `partial` / `missing` / `not_applicable` / `uncertain`, each with
`confidence` (high/medium/low), verbatim `evidence` + page,
`evidence_verified` flag, `human_review` flag.

Guarantees (enforced in code, not prompt):
- summary recounted deterministically — LLM arithmetic never trusted
- every quote checked against the claimed page; TOC-only or unverified
  quotes → `uncertain`
- hallucinated checklist codes dropped; skipped items → `uncertain` +
  human review (never assumed missing)
- parent verdicts rolled up from children; uncertainty propagates up
- per-part pass failure → warning + affected items stay uncertain

## Architecture

```
document (PDF / scanned PDF / DOCX / folder of volumes)
   │
LangGraph workflow: load ─► route by size ─► one pass (small docs)
                                          └► 5 parallel per-part passes (big)
   verify (deterministic): evidence check, roll-up, recount
   │
   ├─► Markdown / Streamlit report
   └─► GraphQL store  ──►  future agents
```

## Tests

```bash
uv run pytest tests/test_agent.py -v -m "not e2e"    # unit (no LLM)
uv run pytest tests/test_agent.py -v -m e2e          # LLM e2e
```
