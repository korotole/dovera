"""Project dossier: many documents, one project, one merged verdict.

Real documentation is split across volumes (reports, drawings, appendices).
A checklist asks about the documentation *as a whole*, so each requirement
is merged across all files:

- strongest verdict wins; its evidence is kept with file attribution
- uncertainty anywhere (and no `present` anywhere) keeps the item uncertain
- a failing file contributes `uncertain`, never a false `missing`
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dovera.checklists.base import Checklist
from dovera.checking.results import CheckResult, Summary, Verdict
from dovera.documents import Document

DOCUMENT_EXTENSIONS = {".pdf", ".docx"}
_VERDICT_RANK = {Verdict.PRESENT: 3, Verdict.PARTIAL: 2, Verdict.UNCERTAIN: 1,
                 Verdict.MISSING: 0, Verdict.NOT_APPLICABLE: 0}


class ProjectChecker:
    """Checks a whole project dossier (folder of documents) as one unit."""

    def __init__(self, model, checklist: Checklist, max_workers: int = 3):
        self.model = model
        self.checklist = checklist
        self.max_workers = max_workers

    def check(self, target: str, progress_cb=None) -> dict:
        paths = self.find_documents(target)
        if not paths:
            raise FileNotFoundError(f"no PDF/DOCX files in {target}")

        per_file: dict[str, dict] = {}
        warnings: list[str] = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {pool.submit(self._check_one, path): path for path in paths}
            for fut in as_completed(futures):
                path = futures[fut]
                out = fut.result()
                per_file[path.name] = out
                if error := out.get("error"):
                    warnings.append(
                        f"Soubor {path.name}: kontrola selhala ({error}) — "
                        "položky, které jen tento soubor mohl doložit, "
                        "zůstávají uncertain.")
                for w in out.get("warnings", []):
                    warnings.append(f"[{path.name}] {w}")
                if progress_cb:
                    progress_cb(path, out)

        results = [self._merge_requirement(req.code, per_file)
                   for req in self.checklist]
        return {
            "results": [r.to_dict() for r in results],
            "summary": Summary.of(results).to_dict(),
            "warnings": warnings,
            "files": {n: (o.get("summary") if "error" not in o
                          else {"error": o["error"]})
                      for n, o in per_file.items()},
            "_meta": {
                "doc_path": str(target),
                "dossier": True,
                "file_count": len(paths),
                "checklist": self.checklist.title,
            },
        }

    @staticmethod
    def find_documents(target: str) -> list[Path]:
        root = Path(target)
        if root.is_file():
            return [root]
        return sorted(p for p in root.iterdir()
                      if p.suffix.lower() in DOCUMENT_EXTENSIONS
                      and not p.name.startswith("."))

    def _check_one(self, path: Path) -> dict:
        from dovera.checking.workflow import DocumentCheckRunner
        from dovera.documents import load_document

        try:
            doc = load_document(str(path))
            return DocumentCheckRunner(self.model, self.checklist).check(doc)
        except Exception as exc:  # noqa: BLE001 — one bad file must not kill the dossier
            return {"error": str(exc), "results": [], "summary": {}}

    # ---- merging ---------------------------------------------------------

    def _merge_requirement(self, code: str, per_file: dict) -> CheckResult:
        req = self.checklist.get(code)
        contributions: list[tuple[str, str, dict | None, str]] = []
        for name, out in per_file.items():
            if "error" in out:
                contributions.append((name, Verdict.UNCERTAIN.value, None,
                                      "soubor se nepodařilo zkontrolovat"))
                continue
            for r in out.get("results", []):
                if r.get("code") == code:
                    contributions.append((name, r["verdict"], r,
                                          r.get("note") or ""))

        best_rank = max((_VERDICT_RANK.get(v, 0) for _, v, _, _ in contributions),
                        default=0)
        best = [c for c in contributions if _VERDICT_RANK.get(c[1], 0) == best_rank]
        merged_verdict = Verdict(best[0][1]) if best else Verdict.UNCERTAIN
        if (merged_verdict != Verdict.PRESENT
                and any(v == Verdict.UNCERTAIN.value for _, v, _, _ in contributions)):
            merged_verdict = Verdict.UNCERTAIN

        result = CheckResult(code=code, title=req.title, verdict=merged_verdict)
        for _name, _v, r, _note in best:  # winning evidence: strongest verdict
            if r and r.get("evidence"):
                result.evidence = r.get("evidence", "")
                result.page = r.get("page")
                result.evidence_verified = bool(r.get("evidence_verified"))
                result.evidence_toc_only = bool(r.get("evidence_toc_only"))
                break
        result.files = {n: v for n, v, _r, _ in contributions}
        result.human_review = (
            any((r or {}).get("human_review") for _, _v, r, _ in contributions)
            or merged_verdict == Verdict.UNCERTAIN)

        notes = [f"[{n}: {v}] {note}" for n, v, _r, note in contributions
                 if note and v in (Verdict.PARTIAL.value, Verdict.MISSING.value,
                                   Verdict.UNCERTAIN.value)]
        if len(per_file) > 1 and result.evidence:
            label = ("Doloženo souborem" if merged_verdict == Verdict.PRESENT
                     else "Nejsilnější důkaz ze svazku")
            source = next(n for n, _v, r, _ in best if r and r.get("evidence"))
            notes.append(f"{label}: {source}")
        result.note = " | ".join(notes)
        return result
