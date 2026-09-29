"""LangGraph workflow for Annex 13 compliance checking.

Deterministic StateGraph around the ReAct checker agent:

    load ──► route ──► check_small (one pass, all items)
                     └► check_big   (per-part passes: A | B | C | D | DOKLADY)
    then verify ──► report (dict assembly; rendering done in report.py)

The graph orchestrates; the LLM agent runs inside `check` nodes; evidence
verification / roll-up / summary recount stay deterministic in agent.py.
"""

from __future__ import annotations

import threading
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

try:  # py3.11+: use the real TimeoutError for future.result(timeout=...)
    FuturesTimeoutError = TimeoutError
except NameError:  # pragma: no cover
    from concurrent.futures import TimeoutError as FuturesTimeoutError

# per-run context for the loaded PdfDocument (LangGraph state is typed:
# non-schema keys like a live document object get filtered out)
_RUN_CTX: dict = {}
_TIMINGS_LOCK = threading.Lock()


class CheckState(TypedDict, total=False):
    # inputs
    doc_path: str
    model: Any
    verbose: bool
    # intermediate
    page_count: int
    is_docx: bool
    ocr_used: bool
    _raw: list[dict]  # raw per-pass agent outputs, merged in verify
    # outputs
    results: list[dict]
    summary: dict[str, int]
    warnings: list[str]
    error: str | None
    meta: dict


# ---------------------------------------------------------------- nodes


def node_load(state: CheckState) -> dict:
    """Load document; note scan/OCR status in warnings. The loaded PdfDocument
    is stashed in a module-level run context (LangGraph filters unknown
    state keys)."""
    from .pdf_tools import load_pdf

    pdf = load_pdf(state["doc_path"])
    _RUN_CTX["pdf"] = pdf
    from .pdf_tools import OCR

    empty = sum(1 for p in pdf.pages if not p)
    warnings: list[str] = []
    if empty:
        warnings.append(
            f"{empty}/{pdf.page_count()} stránky bez extrahovatelného textu "
            "(skeny/výkresy). Verdikty pro jejich obsah jsou nejisté."
        )
    ocr_used = len(OCR.pages) > 0
    return {
        "page_count": pdf.page_count(),
        "is_docx": state["doc_path"].lower().endswith(".docx"),
        "ocr_used": ocr_used,
        "warnings": warnings,
    }


def route_by_size(state: CheckState) -> str:
    """Big docs: per-part agent passes (focused context, less drift).
    Small docs: single pass over all 22 items."""
    return "big" if state["page_count"] > 8 else "small"


def node_check_small(state: CheckState) -> dict:
    raw = _agent_pass(state, prefixes=None)  # all items
    return {"_raw": [raw]}


def node_check_big(state: CheckState) -> dict:
    """Per-part passes run in parallel (tools are read-only over the shared
    PdfDocument). Each pass has a hard timeout: on timeout the part fails
    into warnings and its items stay uncertain — the run never hangs."""
    import time as _time
    from concurrent.futures import ThreadPoolExecutor, as_completed

    prefixes = ("A", "B", "C", "D", "DOKLADY")
    cb = _RUN_CTX.get("progress_cb")
    per_pass_timeout = float(_RUN_CTX.get("per_pass_timeout", 900))
    raws: list = [None] * len(prefixes)
    timings: dict[str, float] = {}

    def run(idx: int, pfx: str):
        t0 = _time.monotonic()
        if cb:
            cb("start", pfx)
        raws[idx] = _agent_pass(state, prefixes=[pfx])
        dt = _time.monotonic() - t0
        with _TIMINGS_LOCK:
            timings[pfx] = dt
            _RUN_CTX["timings"] = dict(timings)
        if cb:
            ok = not raws[idx].get("_failed")
            cb("done", pfx, dt, ok)

    with ThreadPoolExecutor(max_workers=len(prefixes)) as ex:
        futs = {ex.submit(run, i, p): p for i, p in enumerate(prefixes)}
        for fut in as_completed(futs):
            pfx = futs[fut]
            try:
                fut.result(timeout=per_pass_timeout)
            except FuturesTimeoutError:
                raws[prefixes.index(pfx)] = {
                    "_failed": True,
                    "error": f"časový limit {per_pass_timeout:.0f} s pro část [{pfx}]",
                    "prefixes": [pfx],
                }
                if cb:
                    cb("done", pfx, per_pass_timeout, False)

    return {"_raw": [r for r in raws if r is not None]}


def _agent_pass(state: CheckState, prefixes: list[str] | None) -> dict:
    """One agent invocation checking the given checklist slice.
    Returns the raw parsed JSON (or an explicit failure record)."""
    from .agent import SYSTEM_PROMPT, build_agent, run_agent_turn

    try:
        pdf = _RUN_CTX["pdf"]
        agent = build_agent(state["model"], SYSTEM_PROMPT, pdf=pdf)
        return run_agent_turn(agent, pdf, prefixes,
                              state.get("verbose", False),
                              doc_path=state["doc_path"])
    except Exception as exc:  # noqa: BLE001
        return {"_failed": True, "error": f"{type(exc).__name__}: {exc}",
                "prefixes": prefixes}


def node_verify(state: CheckState) -> dict:
    """Deterministic post-pass: normalize, verify evidence, roll up parents,
    recount summary. Reuses agent._verify_results on merged raw results."""
    from .agent import _verify_results

    pdf = _RUN_CTX["pdf"]
    raws = state.get("_raw", [])
    merged: dict[str, Any] = {"results": []}
    warnings = list(state.get("warnings", []))
    for raw in raws:
        if raw.get("_failed"):
            scope = ", ".join(raw.get("prefixes") or ["celý dokument"])
            warnings.append(f"Kontrola části [{scope}] selhala: {raw['error']} — "
                            "příslušné položky zůstávají uncertain.")
            continue
        merged["results"].extend(raw.get("results", []))
        if raw.get("document_title") and not merged.get("document_title"):
            merged["document_title"] = raw["document_title"]
    data = _verify_results(merged, pdf)
    data["_meta"] = {
        "pdf_path": state["doc_path"],
        "pages": pdf.page_count(),
        "checklist": "V_01_260724_Priloha_c_13_Vyhlaska_499_dokumentace_staveb",
        "ocr_used": state.get("ocr_used", False),
        "timings": dict(_RUN_CTX.get("timings", {})),
    }
    data["warnings"] = warnings
    return {"results": data["results"], "summary": data["summary"],
            "document_title": data.get("document_title", ""),
            "meta": data["_meta"]}


# ---------------------------------------------------------------- runner


def build_workflow_graph():
    g = StateGraph(CheckState)
    g.add_node("load", node_load)
    g.add_node("check_small", node_check_small)
    g.add_node("check_big", node_check_big)
    g.add_node("verify", node_verify)
    g.set_entry_point("load")
    g.add_conditional_edges("load", route_by_size,
                            {"small": "check_small", "big": "check_big"})
    g.add_edge("check_small", "verify")
    g.add_edge("check_big", "verify")
    g.add_edge("verify", END)
    return g.compile()


def run_workflow(doc_path: str, model: Any, verbose: bool = False,
                 progress_cb=None, per_pass_timeout: float = 900) -> dict:
    """Entry point. Returns final data dict (results, summary, _meta, warnings).

    ``progress_cb(event, part, duration=None, ok=None)`` gets live per-part
    events for big docs ("start"/"done") — Streamlit shows real progress.
    ``per_pass_timeout`` caps each per-part pass (default 15 min)."""
    from collections import Counter

    _RUN_CTX.clear()
    _RUN_CTX["progress_cb"] = progress_cb
    _RUN_CTX["per_pass_timeout"] = per_pass_timeout
    _RUN_CTX["timings"] = {}
    app = build_workflow_graph()
    try:
        final = app.invoke(
            {"doc_path": doc_path, "model": model, "verbose": verbose},
            config={"recursion_limit": 40},
        )
    finally:
        _RUN_CTX.pop("progress_cb", None)

    counts = Counter(r["verdict"] for r in final["results"])
    summary = {k: counts.get(k, 0)
               for k in ("present", "partial", "missing", "not_applicable", "uncertain")}
    out = {
        "results": final["results"],
        "summary": summary,
        "_meta": final.get("meta", {}),
        "warnings": final.get("warnings", []),
    }
    if final.get("document_title"):
        out["document_title"] = final["document_title"]

    _persist(out)
    return out


def _persist(out: dict) -> None:
    """Best-effort persist to the GraphQL/JSON store (future agents read it
    from there). Failure never breaks the check itself."""
    try:
        from .store import save_workflow_output

        save_workflow_output(out)
    except Exception as exc:  # noqa: BLE001 — persistence is secondary
        import sys
        print(f"[store] WARNING: run not persisted: {exc}", file=sys.stderr)
