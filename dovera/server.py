"""GraphQL HTTP API over the check-result store.

Run: dovera store   (or: python -m dovera.server)
"""

from __future__ import annotations

import json

from ariadne import MutationType, ObjectType, QueryType, make_executable_schema
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from graphql import GraphQLError
from starlette.responses import JSONResponse

from dovera.storage import CheckStore, JsonFileStore

SCHEMA = """
type Summary { present: Int! partial: Int! missing: Int! not_applicable: Int! uncertain: Int! }

type FileVerdict { file: String! verdict: String! }

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
  meta: String!
}

type Query {
  checkRuns(docNameContains: String, limit: Int = 50): [CheckRun!]!
  checkRun(id: ID!): CheckRun
}

input SummaryInput {
  present: Int = 0
  partial: Int = 0
  missing: Int = 0
  not_applicable: Int = 0
  uncertain: Int = 0
}

input FileVerdictInput { file: String! verdict: String! }

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
  id: ID
  docPath: String!
  checklist: String
  summary: SummaryInput!
  warnings: [String!]
  results: [ResultItemInput!]!
  meta: String
}

type Mutation { saveCheckRun(doc: CheckRunInput!): CheckRun! }
"""

_query = QueryType()
_mutation = MutationType()
_summary_type = ObjectType("Summary")
_item_type = ObjectType("ResultItem")

for _f in ("present", "partial", "missing", "not_applicable", "uncertain"):
    _summary_type.set_field(_f, lambda o, i, _f=_f: int(o.get(_f, 0)))

_item_type.set_field("page", lambda o, i: o.get("page"))
_item_type.set_field("evidenceVerified", lambda o, i: bool(o.get("evidence_verified")))
_item_type.set_field("evidenceTocOnly", lambda o, i: bool(o.get("evidence_toc_only")))
_item_type.set_field("humanReview", lambda o, i: bool(o.get("human_review")))
_item_type.set_field("files", lambda o, i: [
    {"file": k, "verdict": v} for k, v in (o.get("files") or {}).items()])


def _bind_run(doc: dict) -> dict:
    return {
        "id": doc["id"], "docPath": doc["doc_path"], "docName": doc["doc_name"],
        "checklist": doc["checklist"], "createdAt": doc["created_at"],
        "updatedAt": doc["updated_at"], "warnings": doc.get("warnings", []),
        "results": doc.get("results", []),
        "summary": doc.get("summary", {}),
        "meta": json.dumps(doc.get("meta", {}), ensure_ascii=False),
    }


_RESULT_KEYS = {"evidenceVerified": "evidence_verified",
                "evidenceTocOnly": "evidence_toc_only",
                "humanReview": "human_review"}


def _result_from_input(item: dict) -> dict:
    out = dict(item)
    for camel, snake in _RESULT_KEYS.items():
        if camel in out:
            out[snake] = out.pop(camel)
    return out


def create_app(store: CheckStore | None = None) -> FastAPI:
    store = store or JsonFileStore()

    @_query.field("checkRuns")
    def resolve_check_runs(_, info, docNameContains=None, limit=50):
        return [_bind_run(d) for d in
                store.list(doc_name_contains=docNameContains or "", limit=limit)]

    @_query.field("checkRun")
    def resolve_check_run(_, info, id):
        doc = store.get(id)
        if doc is None:
            raise GraphQLError(f"CheckRun {id} not found")
        return _bind_run(doc)

    @_mutation.field("saveCheckRun")
    def resolve_save(_, info, doc):
        run = {
            "id": doc.get("id"),
            "doc_path": doc.get("docPath", ""),
            "checklist": doc.get("checklist") or "",
            "summary": doc.get("summary") or {},
            "warnings": doc.get("warnings") or [],
            "results": [_result_from_input(i) for i in doc.get("results") or []],
            "meta": json.loads(doc["meta"]) if doc.get("meta") else {},
        }
        return _bind_run(store.upsert(run))

    schema = make_executable_schema(SCHEMA, _query, _mutation,
                                    _summary_type, _item_type)

    app = FastAPI(title="dovera store")
    app.add_middleware(CORSMiddleware, allow_origins=["*"],
                       allow_methods=["*"], allow_headers=["*"])

    @app.post("/graphql")
    async def graphql_endpoint(request: Request):
        from ariadne import graphql

        body = await request.json()
        _, result = await graphql(
            schema, body, context_value={},
            error_formatter=lambda e, dbg=False: {"message": e.message})
        return JSONResponse(result)

    @app.get("/health")
    async def health():
        return {"ok": True, "runs": len(store.list(limit=1000))}

    return app


def main(port: int = 8700):
    import uvicorn

    uvicorn.run(create_app(), host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
