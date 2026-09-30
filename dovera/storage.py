"""Storage of check results for reuse by other agents/tools.

Default backend: JSON files (zero infrastructure). The GraphQL HTTP API
(`dovera store`) sits on top of the same interface; a DB backend can be
added by implementing `CheckStore`.
"""

from __future__ import annotations

import json
import os
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path



DEFAULT_STORE_DIR = "/tmp/dovera_store"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CheckStore(ABC):
    """Persistence interface for one check run."""

    @abstractmethod
    def upsert(self, run: dict) -> dict: ...

    @abstractmethod
    def get(self, run_id: str) -> dict | None: ...

    @abstractmethod
    def list(self, doc_name_contains: str = "", limit: int = 50) -> list[dict]: ...


class JsonFileStore(CheckStore):
    """One JSON file per run under `store_dir`."""

    def __init__(self, store_dir: str | None = None):
        self.dir = Path(store_dir or os.environ.get("DOVERA_STORE_DIR",
                                                    DEFAULT_STORE_DIR))

    def _path(self, run_id: str) -> Path:
        return self.dir / f"{run_id}.json"

    def upsert(self, run: dict) -> dict:
        self.dir.mkdir(parents=True, exist_ok=True)
        run_id = run.get("id") or uuid.uuid4().hex[:12]
        existing = self.get(run_id)
        doc = {
            "id": run_id,
            "doc_path": run.get("doc_path", ""),
            "doc_name": Path(run.get("doc_path", "")).name,
            "checklist": run.get("checklist", ""),
            "created_at": (existing or {}).get("created_at") or utc_now(),
            "updated_at": utc_now(),
            "summary": run.get("summary", {}),
            "warnings": run.get("warnings", []),
            "results": [self._normalized(r) for r in run.get("results", [])],
            "meta": run.get("meta", {}),
        }
        self._path(run_id).write_text(
            json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        return doc

    def get(self, run_id: str) -> dict | None:
        path = self._path(run_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def list(self, doc_name_contains: str = "", limit: int = 50) -> list[dict]:
        self.dir.mkdir(parents=True, exist_ok=True)
        docs = []
        for path in self.dir.glob("*.json"):
            try:
                docs.append(json.loads(path.read_text(encoding="utf-8")))
            except Exception:  # noqa: BLE001 — one bad file must not break listing
                continue
        if doc_name_contains:
            needle = doc_name_contains.lower()
            docs = [d for d in docs if needle in d.get("doc_name", "").lower()]
        docs.sort(key=lambda d: d.get("updated_at", ""), reverse=True)
        return docs[:limit]

    @staticmethod
    def _normalized(raw: dict) -> dict:
        """`files` is stored as {file: verdict} internally."""
        out = dict(raw)
        files = out.get("files")
        if isinstance(files, list):
            out["files"] = {f["file"]: f["verdict"] for f in files}
        return out


def run_from_check_output(out: dict) -> dict:
    """Adapt a check()/dossier output dict to a store run."""
    meta = out.get("_meta", {})
    return {
        "doc_path": meta.get("doc_path", ""),
        "checklist": meta.get("checklist", ""),
        "summary": out.get("summary", {}),
        "warnings": out.get("warnings", []),
        "results": out.get("results", []),
        "meta": meta,
    }


class StoreUnavailable(RuntimeError):
    pass


def default_store() -> CheckStore:
    return JsonFileStore()
