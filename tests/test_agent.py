"""Regression tests for the Annex 13 checker.

Unit tests (no LLM): checklist data, PDF tools, JSON extraction.
E2E tests (LLM): full runs against synthetic PDFs, asserting verdicts.

Run: uv run pytest tests/ -v
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from invoice_agent.annex13_requirements import REQUIREMENTS, section  # noqa: E402
from invoice_agent.pdf_tools import PdfDocument, load_pdf, search_pages  # noqa: E402

DATA = os.path.join(os.path.dirname(__file__), "data")
COMPLETE = os.path.join(DATA, "complete_project.pdf")
INCOMPLETE = os.path.join(DATA, "incomplete_project.pdf")

LLM_ENV = "ANTHROPIC_AUTH_TOKEN"
needs_llm = pytest.mark.skipif(
    not (os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY")),
    reason="no LLM credentials",
)
e2e = pytest.mark.e2e


# ---------------------------------------------------------------- unit tests


def test_checklist_complete():
    codes = {r.code for r in REQUIREMENTS}
    for expected in ["A", "A.1.1", "A.3", "B", "B.1", "B.2", "C", "C.1", "C.2",
                     "D", "D.1", "D.1.1", "D.1.2", "D.1.3", "D.1.4", "D.2", "DOKLADY"]:
        assert expected in codes, f"missing {expected}"


def test_section_filter():
    assert [r.code for r in section("D.1")] == ["D.1", "D.1.1", "D.1.2", "D.1.3", "D.1.4"]


def test_pdf_load():
    pdf = load_pdf(COMPLETE)
    assert pdf.page_count() >= 3
    assert "PROJEKTOVÁ DOKUMENTACE" in pdf.pages[0]


def test_search_diacritics_insensitive():
    pdf = load_pdf(COMPLETE)
    assert search_pages(pdf, "katastrální území")
    assert search_pages(pdf, "katastralni uzemi")  # no diacritics
    assert not search_pages(pdf, "xyz nonexistent phrase")


def test_verify_results_hardening():
    """Normalization, hallucinated codes dropped, skipped items filled,
    fake quotes downgraded to uncertain, summary recomputed."""
    from invoice_agent.agent import _verify_results

    pdf = load_pdf(COMPLETE)
    data = {"results": [
        {"code": "A.1.1", "verdict": "present",
         "evidence": "Název stavby: Bytový dům Zelená 12", "page": 1},
        {"code": "B.1", "verdict": "PRESENT",
         "evidence": "zzz nonexistent quote zzz", "page": 2},
        {"code": "X.99", "verdict": "weird", "evidence": "", "page": None},
    ]}
    out = _verify_results(data, pdf)
    codes = {r["code"]: r for r in out["results"]}
    assert codes["A.1.1"]["evidence_verified"] is True
    assert codes["B.1"]["evidence_verified"] is False
    # fake evidence must NOT stay 'present' — downgraded to uncertain
    assert codes["B.1"]["verdict"] == "uncertain"
    assert codes["B.1"]["human_review"] is True
    assert "X.99" not in codes                      # hallucinated code dropped
    assert codes["A.2"]["verdict"] == "uncertain"   # skipped -> explicit uncertain
    assert len(out["results"]) == len(REQUIREMENTS)
    assert out["summary"]["uncertain"] >= 20


# ------------------------------------------------------------ LLM pipeline


def _verdicts(path):
    from invoice_agent.agent import check_document
    from invoice_agent.main import build_model

    model = build_model(None)
    return check_document(path, model)


@e2e
@needs_llm
def test_complete_pdf_all_present():
    data = _verdicts(COMPLETE)
    results = {r["code"]: r["verdict"] for r in data["results"]}
    assert len(data["results"]) >= len(REQUIREMENTS)
    bad = {c: v for c, v in results.items()
           if c in {"A.1.1", "B.2", "C.2", "D.1.2", "DOKLADY"} and v != "present"}
    assert not bad, f"expected present, got: {bad}"


@e2e
@needs_llm
def test_incomplete_pdf_flags_missing():
    from invoice_agent.agent import check_document
    from invoice_agent.main import build_model

    model = build_model(None)
    data = check_document(INCOMPLETE, model)
    results = {r["code"]: r["verdict"] for r in data["results"]}
    for code in ["A.2", "B.1", "C.1", "D", "D.1.1", "D.1.2", "D.1.3", "D.1.4", "DOKLADY"]:
        assert results[code] in ("missing", "partial", "uncertain"), \
            f"{code} should be missing/partial/uncertain, got {results[code]}"
    assert results["A.1.1"] == "present"      # názvem a místem stavby
    assert results["A.1.2"] in ("present", "partial")
    # every result must carry confidence + evidence fields (truth tracking)
    for r in data["results"]:
        assert r.get("confidence") in ("high", "medium", "low")


@e2e
@needs_llm
def test_distractor_pdf_no_false_present():
    """Keywords in wrong context (complaint letter) must not yield 'present'
    for structural requirements."""
    from invoice_agent.agent import check_document
    from invoice_agent.main import build_model

    model = build_model(None)
    data = check_document(os.path.join(DATA, "distractor_project.pdf"), model)
    results = {r["code"]: r["verdict"] for r in data["results"]}
    # Nothing can count as fully present: document is a complaint letter,
    # keywords appear out of context. Sections B.*/A.2/A.3 must not be present
    # (missing OR uncertain both honest — uncertainty is allowed, certainty not).
    assert results["B"] in ("missing", "uncertain")
    assert results["A.2"] in ("missing", "uncertain")
    assert results["A.3"] in ("missing", "uncertain")
    falsely_present = {c: v for c, v in results.items() if v == "present"}
    assert not falsely_present, f"false positives: {falsely_present}"


# ------------------------------------------------------------- dossier tests


def test_dossier_find_documents():
    from invoice_agent.dossier import find_documents

    docs = find_documents(DATA)
    names = [p.name for p in docs]
    assert "complete_project.pdf" in names
    assert all(not n.startswith(".") for n in names)
    # single file passthrough
    assert len(find_documents(COMPLETE)) == 1


def test_dossier_merge_logic():
    """Merge/roll-up across volumes with faked per-file workflow results."""
    import pathlib
    import tempfile

    import invoice_agent.dossier as D

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

    def fake_wf(path, model, verbose=False, **kw):
        return responses.pop(0)

    import invoice_agent.workflow
    real = invoice_agent.workflow.run_workflow
    invoice_agent.workflow.run_workflow = fake_wf
    try:
        d = pathlib.Path(tempfile.mkdtemp())
        (d / "a.pdf").write_bytes(b"%PDF-1.4 fake")
        (d / "b.pdf").write_bytes(b"%PDF-1.4 fake")
        (d / "c.pdf").write_bytes(b"%PDF-1.4 fake")
        out = D.run_dossier(str(d), None)
    finally:
        invoice_agent.workflow.run_workflow = real

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


# ---------------------------------------------------------------- fixtures


@pytest.fixture(scope="session", autouse=True)
def _ensure_test_pdfs():
    """Generate synthetic PDFs if absent (they are not committed)."""
    data = os.path.join(os.path.dirname(__file__), "data")
    if not os.path.exists(os.path.join(data, "complete_project.pdf")):
        import subprocess
        subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__),
                                                      "make_test_pdfs.py")],
                       check=True)
