"""Checklist abstraction: what a document type must contain.

A `Checklist` is a tree of `Requirement`s identified by dotted codes
("A", "A.1", "A.1.1"). New document types plug in by registering a
`Checklist` subclass — nothing else in dovera knows which checklist is in
use; the checker, verifier, reporter and store all take it as a parameter.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Requirement:
    """One checkable item."""

    code: str
    title: str
    description: str
    keywords: tuple[str, ...] = ()
    not_applicable_allowed: bool = False

    @property
    def parent_code(self) -> str | None:
        return self.code.rsplit(".", 1)[0] if "." in self.code else None


class Checklist:
    """Ordered set of requirements for one document type."""

    title: str = "Checklist"

    def __init__(self, requirements: list[Requirement]):
        self.requirements = requirements
        self._by_code = {r.code: r for r in requirements}

    def __iter__(self):
        return iter(self.requirements)

    def __len__(self) -> int:
        return len(self.requirements)

    def __contains__(self, code: str) -> bool:
        return code in self._by_code

    def get(self, code: str) -> Requirement:
        return self._by_code[code]

    def matching(self, code_prefix: str) -> list[Requirement]:
        if not code_prefix:
            return list(self.requirements)
        return [r for r in self.requirements
                if r.code == code_prefix or r.code.startswith(code_prefix + ".")]

    def children_of(self, code: str) -> list[Requirement]:
        return [r for r in self.requirements if r.parent_code == code]

    def codes(self) -> set[str]:
        return set(self._by_code)

    def describe(self, code_prefix: str = "") -> str:
        lines = [f"[{r.code}] {r.title}\n  {r.description}"
                 for r in self.matching(code_prefix)]
        return "\n".join(lines) or f"No requirements for prefix '{code_prefix}'."

    def prompt_scope(self, prefixes: list[str] | None) -> str:
        if not prefixes:
            return ""
        return ("Zkontroluj POUZE položky s kódy začínajícími na: "
                f"{', '.join(prefixes)}. Jiné položky NEVypisuj.")


class ChecklistRegistry:
    """Maps checklist names to instances; loaded from the registry package
    or extended programmatically (custom document types)."""

    _checklists: dict[str, Checklist] = {}

    @classmethod
    def register(cls, checklist: Checklist, name: str | None = None) -> None:
        cls._checklists[name or checklist.title] = checklist

    @classmethod
    def get(cls, name: str) -> Checklist:
        if not cls._checklists:
            cls.load_builtins()
        try:
            return cls._checklists[name]
        except KeyError:
            known = ", ".join(sorted(cls._checklists)) or "(none)"
            raise KeyError(f"unknown checklist '{name}' (known: {known})")

    @classmethod
    def names(cls) -> list[str]:
        if not cls._checklists:
            cls.load_builtins()
        return sorted(cls._checklists)

    @classmethod
    def load_builtins(cls) -> None:
        from dovera.checklists.annex13 import Annex13Checklist

        if "annex13" not in cls._checklists:
            cls.register(Annex13Checklist(), "annex13")
