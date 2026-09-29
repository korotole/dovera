"""GraphQL store for check results — for reuse by future agents.

FastAPI + Ariadne over a JSON-file-backed repository (no external DB;
each check run is one document). The same storage interface can later be
re-pointed at Postgres etc. without changing the schema.

Run standalone:  uv run python -m invoice_agent.store   (port 8700)

Schema (see store_schema.graphql):
  - query checkRuns(...) : [CheckRun!]!          search saved runs
  - query checkRun(id)   : CheckRun              one run with per-item results
  - mutation saveCheckRun(doc) : CheckRun!      persist one run (idempotent upsert)
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone

from fastapi import Request  # noqa: F401 — needed at module scope for pydantic
                             # to resolve the endpoint parameter annotation
from pathlib import Path

# ------------------------------------------------------------------ storage

STORE_DIR = Path(os.environ.get("ANNEX13_STORE_DIR", "/tmp/annex13_store"))


def _doc_path(run_id: str) -> Path:
    return STORE_DIR / f"{run_id}.json"


def _load(run_id: str) -> dict | None:
    p = _doc_path(run_id)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def _save(doc: dict) -> dict:
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    _doc_path(doc["id"]).write_text(
        json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return doc


def upsert_check_run(data: dict) -> dict:
    """Upsert one check run. ``doc_sha`` makes it idempotent per document."""
    doc_id = data.get("id") or uuid.uuid4().hex[:12]
    now = datetime.now(timezone.utc).isoformat()
    existing = _load(doc_id)
    # normalize results: `files` is stored as {file: verdict} internally
    results = []
    for r in data.get("results", []):
        r = dict(r)
        files = r.get("files")
        if isinstance(files, list):
            r["files"] = {f["file"]: f["verdict"] for f in files}
        results.append(r)
    doc = {
        "id": doc_id,
        "doc_path": data.get("doc_path", ""),
        "doc_name": Path(data.get("doc_path", "")).name,
        "checklist": data.get("checklist", "V_01_260724_Priloha_c_13_Vyhlaska_499_dokumentace_staveb"),
        "created_at": existing["created_at"] if existing else now,
        "updated_at": now,
        "summary": data.get("summary", {}),
        "warnings": data.get("warnings", []),
        "results": results,
        "meta": data.get("meta", {}),
    }
    _save(doc)
    return doc


def list_check_runs(**filters) -> list[dict]:
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    docs = []
    for p in sorted(STORE_DIR.glob("*.json")):
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 — one bad file must not break listing
            continue
        if filters.get("doc_name_contains") and filters["doc_name_contains"].lower() not in doc.get("doc_name", "").lower():
            continue
        if filters.get("since") and doc.get("updated_at", "") < filters["since"]:
            continue
        docs.append(doc)
    docs.sort(key=lambda d: d.get("updated_at", ""), reverse=True)
    return docs[: filters.get("limit", 50)]


def save_workflow_output(out: dict) -> dict:
    """Convenience: persist the dict returned by run_workflow/run_dossier."""
    meta = out.get("_meta", {})
    return upsert_check_run({
        "doc_path": meta.get("pdf_path", ""),
        "checklist": meta.get("checklist", ""),
        "summary": out.get("summary", {}),
        "warnings": out.get("warnings", []),
        "results": out.get("results", []),
        "meta": meta,
    })


# ------------------------------------------------------------------ GraphQL

SCHEMA = """
type Summary {
  present: Int!
  partial: Int!
  missing: Int!
  not_applicable: Int!
  uncertain: Int!
}

type ResultItem {
  code: String!
  title: String
  verdict: String!
  confidence: String
  evidence: String
  page: Int
  evidenceVerified: Boolean
  evidenceTocOnly: Boolean
  humanReview: Boolean
  note: String
  files: [FileVerdict!]
}

type FileVerdict {
  file: String!
  verdict: String!
}

type CheckRun {
  id: ID!
  docPath: String!
  docName: String!
  checklist: String!
  createdAt: String!
  updatedAt: String!
  summary: Summary!
  warnings: [String!]!
  results: [ResultItem!]!
  meta: String!            # raw JSON blob (varies per run type)
}

type Query {
  checkRuns(docNameContains: String, since: String, limit: Int = 50): [CheckRun!]!
  checkRun(id: ID!): CheckRun
}

input SummaryInput {
  present: Int = 0
  partial: Int = 0
  missing: Int = 0
  not_applicable: Int = 0
  uncertain: Int = 0
}

input FileVerdictInput {
  file: String!
  verdict: String!
}

input ResultItemInput {
  code: String!
  title: String
  verdict: String!
  confidence: String
  evidence: String
  page: Int
  evidenceVerified: Boolean
  evidenceTocOnly: Boolean
  humanReview: Boolean
  note: String
  files: [FileVerdictInput!]
}

input CheckRunInput {
  id: ID                      # optional; upsert when given
  docPath: String!
  checklist: String
  summary: SummaryInput!
  warnings: [String!]
  results: [ResultItemInput!]!
  meta: String
}

type Mutation {
  saveCheckRun(doc: CheckRunInput!): CheckRun!
}
"""


def _bind_doc(doc: dict) -> dict:
    """Attach camelCase object_types accessors used by Ariadne converters."""
    return doc


def create_app():
    from ariadne import MutationType, ObjectType, QueryType, make_executable_schema
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from graphql import GraphQLError

    query = QueryType()
    mutation = MutationType()

    summary_obj = ObjectType("Summary")
    for f in ("present", "partial", "missing", "not_applicable", "uncertain"):
        summary_obj.set_field(f, lambda o, i, _f=f: int(o.get(_f, 0)))

    item_obj = ObjectType("ResultItem")
    item_obj.set_field("files", lambda o, i: [
        {"file": k, "verdict": v} for k, v in (o.get("files") or {}).items()])

    def bind_run(doc):
        return {
            "id": doc["id"], "docPath": doc["doc_path"], "docName": doc["doc_name"],
            "checklist": doc["checklist"], "createdAt": doc["created_at"],
            "updatedAt": doc["updated_at"], "warnings": doc.get("warnings", []),
            "results": doc.get("results", []), "meta": json.dumps(doc.get("meta", {}),
                                                                 ensure_ascii=False),
            "summary": doc.get("summary", {}),
        }

    @query.field("checkRuns")
    def resolve_check_runs(_, info, docNameContains=None, since=None, limit=50):
        return [bind_run(d) for d in
                list_check_runs(doc_name_contains=docNameContains, since=since,
                                limit=limit)]

    @query.field("checkRun")
    def resolve_check_run(_, info, id):
        doc = _load(id)
        if doc is None:
            raise GraphQLError(f"CheckRun {id} not found")
        return bind_run(doc)

    @mutation.field("saveCheckRun")
    def resolve_save(_, info, doc):
        out = upsert_check_run({
            "id": doc.get("id") or uuid.uuid4().hex[:12],
            "doc_path": doc.get("docPath", ""),
            "checklist": doc.get("checklist") or "",
            "summary": doc.get("summary") or {},
            "warnings": doc.get("warnings") or [],
            "results": doc.get("results") or [],
            "meta": json.loads(doc["meta"]) if doc.get("meta") else {},
        })
        return bind_run(out)

    schema = make_executable_schema(SCHEMA, query, mutation, summary_obj, item_obj)

    app = FastAPI(title="Annex 13 GraphQL store")
    app.add_middleware(CORSMiddleware, allow_origins=["*"],
                       allow_methods=["*"], allow_headers=["*"])

    @app.post("/graphql")
    async def graphql_endpoint(request: Request):
        from ariadne import graphql
        from starlette.responses import JSONResponse

        body = await request.json()
        _, result = await graphql(schema, body, context_value={},
                                  error_formatter=lambda e, dbg=False:
                                      {"message": e.message},
                                  debug=False)
        return JSONResponse(result)


    @app.get("/health")
    async def health():
        return {"ok": True, "runs": len(list_check_runs(limit=1000))}

    return app


def main(port: int = 8700):
    import uvicorn

    uvicorn.run(create_app(), host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
