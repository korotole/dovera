"""High-level pipeline: the one class callers interact with.

    from dovera.pipeline import Dovers

    dovers = Dovers(model)
    out = dovers.check("doc.pdf")                    # single document
    out = dovers.check("/project-folder/")           # whole dossier
    out = dovers.check("doc.pdf", checklist="annex13")

Results are persisted best-effort (failure never breaks the check).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from dovera.checking.dossier import ProjectChecker
from dovera.checking.results import CheckResult
from dovera.checking.workflow import DocumentCheckRunner
from dovera.checklists.base import Checklist, ChecklistRegistry
from dovera.documents import load_document
from dovera.storage import CheckStore, JsonFileStore, run_from_check_output


class Dovers:
    """Facade over the whole check pipeline."""

    def __init__(self, model: Any, checklist: str = "annex13",
                 store: CheckStore | None = None,
                 per_pass_timeout: float = 900.0):
        self.model = model
        self.checklist = ChecklistRegistry.get(checklist)
        self.store = store or JsonFileStore()
        self.per_pass_timeout = per_pass_timeout

    def check(self, target: str, progress_cb=None) -> dict:
        """Check a file or a folder (dossier). Returns the output dict."""
        if Path(target).is_dir():
            out = ProjectChecker(self.model, self.checklist).check(
                target, progress_cb=progress_cb)
        else:
            doc = load_document(target)
            out = DocumentCheckRunner(self.model, self.checklist,
                                      per_pass_timeout=self.per_pass_timeout
                                      ).check(doc, progress_cb=progress_cb)
        self._persist(out)
        return out

    @staticmethod
    def verdicts(out: dict) -> dict[str, CheckResult]:
        return {r["code"]: CheckResult.from_dict(r) for r in out["results"]}

    def _persist(self, out: dict) -> None:
        try:
            self.store.upsert(run_from_check_output(out))
        except Exception as exc:  # noqa: BLE001 — persistence is secondary
            print(f"[dovera] WARNING: run not persisted: {exc}", file=sys.stderr)
