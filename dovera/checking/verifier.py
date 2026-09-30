"""Deterministic post-processing of raw agent verdicts.

The LLM proposes; this module disposes. Every guarantee is enforced here,
never in the prompt:
- unknown verdict strings / hallucinated codes / skipped items become
  `uncertain` (never certainty, never silent absence)
- quoted evidence must exist on the claimed page; unverifiable or TOC-only
  quotes downgrade the verdict to `uncertain` + human review
- parent-section verdicts roll up from children; uncertainty propagates
"""

from __future__ import annotations

import re

from dovera.checklists.base import Checklist
from dovera.checking.results import CheckResult, Confidence, Summary, Verdict
from dovera.documents import Document, normalize_text, squash

_QUOTE_SPLITS = re.compile(r"/|\.\.\.|…")
_CONFIDENCE_ORDER = {Confidence.HIGH: 0, Confidence.MEDIUM: 1, Confidence.LOW: 2}


class EvidenceVerifier:
    """Checks quoted evidence against the document text."""

    def __init__(self, doc: Document):
        self.doc = doc

    def verify(self, result: CheckResult) -> None:
        """In-place: set evidence_verified / evidence_toc_only; downgrade
        verdicts whose quotes cannot be found on the claimed page."""
        evidence = result.evidence.strip()
        if result.verdict not in (Verdict.PRESENT, Verdict.PARTIAL) or not evidence:
            return
        page = result.page
        if not (isinstance(page, int) and 1 <= page <= self.doc.page_count()):
            self._downgrade(result, f"uvedena neplatná strana ({page})")
            return
        page_text = squash(normalize_text(self.doc.pages[page - 1]))
        needle = squash(normalize_text(evidence))
        if not self._found(page_text, needle):
            self._downgrade(result, f"citát se nepodařilo najít na straně {page}")
            return
        if page in self.doc.toc_pages:
            result.evidence_toc_only = True
            result.evidence_verified = False
            result.verdict = Verdict.UNCERTAIN
            result.human_review = True
            result.note = ("Citát pochází z OBSAHU — dokazuje jen existenci "
                           "nadpisu, ne skutečného obsahu. Verdikt degradován "
                           "na uncertain. " + result.note).strip()
        else:
            result.evidence_verified = True

    @staticmethod
    def _found(page_text: str, needle: str) -> bool:
        if len(needle) >= 15 and needle in page_text:
            return True
        for size in (60, 40, 25):
            if len(needle) >= size and needle[:size] in page_text:
                return True
        frags = [f.strip(" .,/…") for f in _QUOTE_SPLITS.split(needle)]
        frags = [f for f in frags if len(f) >= 12]
        return bool(frags) and all(f in page_text for f in frags)

    @staticmethod
    def _downgrade(result: CheckResult, reason: str) -> None:
        result.evidence_verified = False
        if result.verdict == Verdict.UNCERTAIN:
            return
        original = result.verdict.value
        result.verdict = Verdict.UNCERTAIN
        result.human_review = True
        result.note = (f"UVEDENÝ CITÁT NEPODPOŘEN ({reason}) — verdikt "
                       f"degradován na uncertain. Původní verdikt: {original}. "
                       + result.note).strip()


class ResultNormalizer:
    """Raw LLM dict -> trustworthy CheckResult list."""

    def __init__(self, checklist: Checklist):
        self.checklist = checklist

    def normalize(self, raw: dict) -> list[CheckResult]:
        results: dict[str, CheckResult] = {}
        for item in raw.get("results", []):
            code = str(item.get("code", "")).strip()
            if code not in self.checklist:
                continue  # hallucinated checklist code
            result = CheckResult.from_dict(item)
            result.title = self.checklist.get(code).title
            if str(item.get("verdict", "")).strip().lower() not in Verdict._value2member_map_:
                result.verdict = Verdict.UNCERTAIN
                result.human_review = True
                result.note = (f"Neznámý verdikt '{item.get('verdict')}' od "
                               "agenta — vyžaduje lidské posouzení. "
                               + result.note).strip()
            results[code] = result
        for req in self.checklist:  # skipped items: explicit uncertain
            if req.code not in results:
                results[req.code] = CheckResult(
                    code=req.code, title=req.title,
                    note="Agent nevydal verdikt — vyžaduje lidské posouzení.")
        return list(results.values())


class ResultMerger:
    """Verify, roll up parents, and recount — the deterministic pipeline."""

    def __init__(self, checklist: Checklist, doc: Document):
        self.checklist = checklist
        self.verifier = EvidenceVerifier(doc)

    def finalize(self, raw_results: list[dict]) -> list[CheckResult]:
        normalized = ResultNormalizer(self.checklist).normalize(
            {"results": raw_results})
        for result in normalized:
            self.verifier.verify(result)
        by_code = {r.code: r for r in normalized}
        self._roll_up(by_code)
        ordered = [by_code[r.code] for r in self.checklist]
        return ordered

    @staticmethod
    def summarize(results: list[CheckResult]) -> dict[str, int]:
        return Summary.of(results).to_dict()

    def _roll_up(self, results: dict[str, CheckResult]) -> None:
        for parent in (r.code for r in self.checklist):
            children = self.checklist.children_of(parent)
            if not children:
                continue
            kids = [results[req.code] for req in children if req.code in results]
            if not kids:
                continue
            verdicts = [k.verdict for k in kids]
            if all(v == Verdict.NOT_APPLICABLE for v in verdicts):
                rolled = Verdict.NOT_APPLICABLE
            elif all(v == Verdict.PRESENT for v in verdicts):
                rolled = Verdict.PRESENT
            elif all(v == Verdict.MISSING for v in verdicts):
                rolled = Verdict.MISSING
            elif any(v == Verdict.UNCERTAIN for v in verdicts):
                rolled = Verdict.UNCERTAIN
            else:
                rolled = Verdict.PARTIAL
            parent_result = results[parent]
            if parent_result.verdict != rolled:
                parent_result.note = (parent_result.note +
                    f" [Verdict části přepočítán z podpoložek: {rolled.value}.]").strip()
            parent_result.verdict = rolled
            if any(k.human_review for k in kids):
                parent_result.human_review = True
            parent_result.confidence = max(
                (k.confidence for k in kids),
                key=lambda c: list(Confidence).index(c))
