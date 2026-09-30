"""ReAct checker agent: searches the document for evidence per requirement.

The agent is document-type-agnostic: it receives the checklist through its
tools, so the same loop checks any `Checklist`. Verification of its output
happens in `verifier.py` — never trust the model here.
"""

from __future__ import annotations

import json
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool

from dovera.checklists.base import Checklist
from dovera.documents import Document, search_pages

RECURSION_LIMIT = 120


def build_tools(checklist: Checklist, doc: Document) -> list:
    """The three evidence tools, bound to one checklist + one document."""

    @tool
    def get_requirements(code_prefix: str = "") -> str:
        """Get checklist items. Pass empty string for all items, or a code
        prefix like 'A', 'A.1', 'B.2' to filter. Returns code, title and
        description for each requirement."""
        return checklist.describe(code_prefix)

    @tool
    def search_document(query: str) -> str:
        """Search the document text for a phrase (Czech, diacritics-insensitive).
        Returns up to 10 hits as 'page N: ...excerpt...' lines. Hits marked
        [TOC] are from the table of contents — they show only that a headline
        exists, NOT that the content is there. Never use a TOC hit alone as
        evidence for 'present'. Use short distinctive phrases, e.g. from the
        requirement's keywords."""
        hits = search_pages(doc, query)
        if not hits:
            return f"No hits for '{query}'. Try different wording."
        return "\n".join(
            f"page {h['page']}" + (" [TOC]" if h.get("toc") else "") +
            f": {h['excerpt']}" for h in hits)

    @tool
    def read_page(page_number: int) -> str:
        """Read full text of one page (1-based). Use after a search hit or to
        inspect a page that looks like it contains a required section."""
        if page_number < 1 or page_number > doc.page_count():
            return (f"Invalid page {page_number}. Document has "
                    f"{doc.page_count()} pages.")
        text = doc.pages[page_number - 1]
        if not text:
            return (f"Page {page_number} has no extractable text "
                    "(scan/image page? content may exist in a drawing — "
                    "verdict must be uncertain with human_review).")
        return text

    return [get_requirements, search_document, read_page]


def build_agent(model: Any, checklist: Checklist, doc: Document,
                system_prompt: str):
    return create_agent(model, build_tools(checklist, doc),
                        system_prompt=system_prompt)


def extract_json(text: str) -> dict[str, Any]:
    """Pull the first JSON object out of an LLM reply."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON object in reply: {text[:200]!r}")
    return json.loads(text[start:end + 1])


def _content_text(message) -> str:
    content = message.content
    if isinstance(content, list):  # some providers return content blocks
        return "".join(b.get("text", "") for b in content if isinstance(b, dict))
    return content


class CheckerAgent:
    """One agent conversation checking a slice of the checklist."""

    def __init__(self, model: Any, checklist: Checklist, doc: Document,
                 system_prompt: str, doc_context: str = ""):
        self.agent = build_agent(model, checklist, doc, system_prompt)
        self.checklist = checklist
        self.doc = doc
        self.doc_context = doc_context

    def run(self, prefixes: list[str] | None = None, verbose: bool = False,
            max_retries: int = 2) -> dict:
        """Returns raw parsed JSON ({document_title, results, summary})."""
        scope = self.checklist.prompt_scope(prefixes)
        state = {"messages": [HumanMessage(
            content=f"Zkontroluj dokument. {self.doc_context} {scope} "
                    "Vrať finální JSON s verdikty pro příslušné položky "
                    "kontrolního seznamu.")]}
        config = {"recursion_limit": RECURSION_LIMIT}

        for attempt in range(3):
            try:
                state = self.agent.invoke(state, config=config)
            except Exception as exc:  # includes GraphRecursionError
                if "recursion" in str(exc).lower() and attempt < 2:
                    state["messages"].append(HumanMessage(content=(
                        "Dosažen limit kroků. Na základě toho, co už víš, "
                        "vyzvy verdikty jen pro položky, ke kterým máš důkazy, "
                        "a VRAŤ teď finální JSON (ostatní položky vědomě VYPUSŤ "
                        "— doplní se jako uncertain). Žádný jiný text.")))
                    continue
                raise
            text = _content_text(state["messages"][-1])
            try:
                return extract_json(text)
            except (ValueError, json.JSONDecodeError) as exc:
                if attempt >= 2:
                    raise
                state["messages"].append(HumanMessage(content=(
                    "Tvoje odpověď nebyla platný JSON. Vrať POUZE jeden platný "
                    "JSON objekt bez komentářů a bez markdown fencing, "
                    "s položkami kontrolního seznamu.")))
        raise ValueError("agent did not produce valid JSON in time")
