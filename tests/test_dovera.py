"""dovera regression tests.

Unit tests (no LLM): checklist data, documents, verifier, dossier merge,
storage. E2E tests (LLM): full runs against synthetic PDFs.

Run: uv run pytest tests/ -v
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dovera.checking.dossier import ProjectChecker  # noqa: E402
from dovera.checking.results import Verdict  # noqa: E402
from dovera.checking.verifier import ResultMerger  # noqa: E402
from dovera.checklists import ChecklistRegistry  # noqa: E402
from dovera.documents import load_document, search_pages  # noqa: E402
from dovera.storage import JsonFileStore  # noqa: E402

DATA = os.path.join(os.path.dirname(__file__), "data")
COMPLETE = os.path.join(DATA, "complete_project.pdf")
INCOMPLETE = os.path.join(DATA, "incomplete_project.pdf")

needs_llm = pytest.mark.skipif(
    not (os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY")),
    reason="no LLM credentials")
e2e = pytest.mark.e2e


def _checklist():
    return ChecklistRegistry.get("annex13")


# ---------------------------------------------------------------- unit tests


def test_checklist_complete():
    codes = _checklist().codes()
    for expected in ["A", "A.1.1", "A.3", "B", "B.1", "B.2", "C", "C.1", "C.2",
                     "D", "D.1", "D.1.1", "D.1.2", "D.1.3", "D.1.4", "D.2", "DOKLADY"]:
        assert expected in codes, f"missing {expected}"


def test_checklist_section_filter():
    assert [r.code for r in _checklist().matching("D.1")] == \
        ["D.1", "D.1.1", "D.1.2", "D.1.3", "D.1.4"]
    assert _checklist().children_of("D.1") and \
        all(r.parent_code == "D.1" for r in _checklist().children_of("D.1"))


def test_pdf_load():
    doc = load_document(COMPLETE)
    assert doc.page_count() >= 3
    assert "PROJEKTOVÁ DOKUMENTACE" in doc.pages[0]


def test_search_diacritics_insensitive():
    doc = load_document(COMPLETE)
    assert search_pages(doc, "katastrální území")
    assert search_pages(doc, "katastralni uzemi")  # no diacritics
    assert not search_pages(doc, "xyz nonexistent phrase")


def test_verifier_hardening():
    """Verified quote stays present; fake quote downgraded to uncertain;
    hallucinated codes dropped; skipped items filled as uncertain."""
    checklist = _checklist()
    doc = load_document(COMPLETE)
    raw = [
        {"code": "A.1.1", "verdict": "present",
         "evidence": "Název stavby: Bytový dům Zelená 12", "page": 1},
        {"code": "B.1", "verdict": "PRESENT",
         "evidence": "zzz nonexistent quote zzz", "page": 2},
        {"code": "X.99", "verdict": "weird", "evidence": "", "page": None},
    ]
    merger = ResultMerger(checklist, doc)
    results = merger.finalize(raw)
    by_code = {r.code: r for r in results}
    assert by_code["A.1.1"].evidence_verified is True
    assert by_code["B.1"].verdict == Verdict.UNCERTAIN
    assert by_code["B.1"].human_review is True
    assert "X.99" not in by_code                       # hallucinated dropped
    assert by_code["A.2"].verdict == Verdict.UNCERTAIN  # skipped -> uncertain
    assert len(results) == len(checklist)
    assert sum(1 for r in results if r.verdict == Verdict.UNCERTAIN) >= 20


def test_dossier_find_documents():
    docs = ProjectChecker.find_documents(DATA)
    names = [p.name for p in docs]
    assert "complete_project.pdf" in names
    assert all(not n.startswith(".") for n in names)
    assert len(ProjectChecker.find_documents(COMPLETE)) == 1


def test_dossier_merge_logic():
    """Merge/roll-up across volumes with faked per-file check results."""
    import tempfile

    fake_present = {"results": [
        {"code": "A", "verdict": "present", "evidence": "x", "page": 1,
         "evidence_verified": True, "human_review": False, "note": ""}],
        "summary": {"present": 1}, "warnings": []}
    fake_missing = {"results": [
        {"code": "A", "verdict": "missing", "evidence": "", "page": None,
         "evidence_verified": False, "human_review": False, "note": ""}],
        "summary": {"missing": 1}, "warnings": []}
    fake_broken = {"error": "boom", "results": [], "summary": {}}

    responses = [fake_present, fake_missing, fake_broken]

    def fake_check_one(self, path):
        return responses.pop(0)

    real = ProjectChecker._check_one
    ProjectChecker._check_one = fake_check_one
    try:
        d = Path(tempfile.mkdtemp())
        for name in ("a.pdf", "b.pdf", "c.pdf"):
            (d / name).write_bytes(b"%PDF-1.4 fake")
        out = ProjectChecker(model=None, checklist=_checklist()).check(str(d))
    finally:
        ProjectChecker._check_one = real

    r = {x["code"]: x for x in out["results"]}
    # A: present in one file, missing in another, third file broken ->
    #    present wins (verified evidence), broken file noted
    assert r["A"]["verdict"] == "present"
    assert r["A"]["evidence_verified"]
    assert any("selhala" in (r["A"].get("note") or "") or
               "selhala" in w for w in out["warnings"])
    assert out["_meta"]["dossier"] and out["_meta"]["file_count"] == 3
    assert len(r["A"].get("files", {})) == 3
    # items no file said anything about -> uncertain, no file attribution
    other = next(x for x in out["results"] if x["code"] != "A")
    assert other["verdict"] == "uncertain" and other["human_review"]


def test_store_roundtrip():
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        store = JsonFileStore(d)
        run = store.upsert({"doc_path": "/x/projekt.pdf", "checklist": "annex13",
                            "summary": {"present": 2, "uncertain": 20},
                            "warnings": [], "results": [
                                {"code": "A", "verdict": "present",
                                 "files": {"a.pdf": "present"}}],
                            "meta": {"dossier": True}})
        got = store.get(run["id"])
        assert got["doc_name"] == "projekt.pdf"
        assert got["results"][0]["files"] == {"a.pdf": "present"}
        assert store.list(doc_name_contains="projekt")
        assert not store.list(doc_name_contains="nope")


# ---------------------------------------------------------------- LLM e2e


def _check(path):
    from dovera.cli import build_model
    from dovera.pipeline import Dovers

    return Dovers(build_model(None, os.environ.get("DOVERA_BACKEND"))).check(path)


@e2e
@needs_llm
def test_complete_pdf_all_present():
    out = _check(COMPLETE)
    results = {r["code"]: r["verdict"] for r in out["results"]}
    bad = {c: v for c, v in results.items()
           if c in {"A.1.1", "B.2", "C.2", "D.1.2", "DOKLADY"} and v != "present"}
    assert not bad, f"expected present, got: {bad}"


@e2e
@needs_llm
def test_incomplete_pdf_flags_missing():
    out = _check(INCOMPLETE)
    results = {r["code"]: r["verdict"] for r in out["results"]}
    for code in ["A.2", "B.1", "C.1", "D", "D.1.1", "D.1.2", "D.1.3", "D.1.4", "DOKLADY"]:
        assert results[code] in ("missing", "partial", "uncertain"), \
            f"{code} should be missing/partial/uncertain, got {results[code]}"
    assert results["A.1.1"] == "present"
    assert results["A.1.2"] in ("present", "partial")
    for r in out["results"]:
        assert r.get("confidence") in ("high", "medium", "low")


@e2e
@needs_llm
def test_distractor_pdf_no_false_present():
    """Keywords in wrong context (complaint letter) must not yield 'present'."""
    out = _check(os.path.join(DATA, "distractor_project.pdf"))
    results = {r["code"]: r["verdict"] for r in out["results"]}
    assert results["B"] in ("missing", "uncertain")
    assert results["A.2"] in ("missing", "uncertain")
    assert results["A.3"] in ("missing", "uncertain")
    falsely_present = {c: v for c, v in results.items() if v == "present"}
    assert not falsely_present, f"false positives: {falsely_present}"


# ---------------------------------------------------------------- fixtures


@pytest.fixture(scope="session", autouse=True)
def _ensure_test_pdfs():
    """Generate synthetic PDFs if absent (they are not committed)."""
    if not os.path.exists(COMPLETE):
        import subprocess

        subprocess.run([sys.executable,
                        os.path.join(os.path.dirname(__file__), "make_test_pdfs.py")],
                       check=True)
