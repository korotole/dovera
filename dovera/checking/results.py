"""Core result model: verdicts, confidence, evidence, roll-up.

A `CheckResult` is one requirement's outcome. `Summary` recounts verdicts
deterministically — LLM arithmetic is never trusted.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from enum import Enum


class Verdict(str, Enum):
    PRESENT = "present"
    PARTIAL = "partial"
    MISSING = "missing"
    NOT_APPLICABLE = "not_applicable"
    UNCERTAIN = "uncertain"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


_RANK = {Verdict.PRESENT: 3, Verdict.PARTIAL: 2, Verdict.UNCERTAIN: 1,
         Verdict.MISSING: 0, Verdict.NOT_APPLICABLE: 0}


@dataclass
class CheckResult:
    """Verdict for one requirement, with its evidence and review state."""

    code: str
    title: str = ""
    verdict: Verdict = Verdict.UNCERTAIN
    confidence: Confidence = Confidence.LOW
    evidence: str = ""
    page: int | None = None
    evidence_verified: bool = False
    evidence_toc_only: bool = False
    human_review: bool = True
    note: str = ""
    files: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = {
            "code": self.code, "title": self.title,
            "verdict": self.verdict.value, "confidence": self.confidence.value,
            "evidence": self.evidence, "page": self.page,
            "evidence_verified": self.evidence_verified,
            "evidence_toc_only": self.evidence_toc_only,
            "human_review": self.human_review, "note": self.note,
        }
        if self.files:
            d["files"] = dict(self.files)
        return d

    @classmethod
    def from_dict(cls, raw: dict) -> "CheckResult":
        return cls(
            code=str(raw.get("code", "")).strip(),
            title=raw.get("title", ""),
            verdict=_safe_verdict(raw.get("verdict")),
            confidence=_safe_confidence(raw.get("confidence")),
            evidence=str(raw.get("evidence") or ""),
            page=raw.get("page") if isinstance(raw.get("page"), int) else None,
            evidence_verified=bool(raw.get("evidence_verified")),
            evidence_toc_only=bool(raw.get("evidence_toc_only")),
            human_review=bool(raw.get("human_review", True)),
            note=str(raw.get("note") or ""),
            files=dict(raw.get("files") or {}),
        )


@dataclass
class Summary:
    counts: dict[Verdict, int] = field(default_factory=dict)

    @classmethod
    def of(cls, results: list["CheckResult"]) -> "Summary":
        counter = Counter(r.verdict for r in results)
        return cls({v: counter.get(v, 0) for v in Verdict})

    def to_dict(self) -> dict:
        return {v.value: n for v, n in self.counts.items()}


def _safe_verdict(raw) -> Verdict:
    try:
        return Verdict(str(raw).strip().lower())
    except ValueError:
        return Verdict.UNCERTAIN


def _safe_confidence(raw) -> Confidence:
    try:
        return Confidence(str(raw).strip().lower())
    except ValueError:
        return Confidence.LOW
