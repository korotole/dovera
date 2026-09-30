"""Document checking pipeline: load -> route by size -> check -> verify.

Small documents get one agent pass over the whole checklist; large ones get
per-part passes run in parallel (each with a hard timeout — a hung pass
fails into warnings, its items stay uncertain, the run never hangs).
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError

from dovera.checklists.base import Checklist
from dovera.checking.agent import CheckerAgent
from dovera.checking.prompt import build_system_prompt
from dovera.checking.verifier import ResultMerger
from dovera.documents import Document

SMALL_DOC_MAX_PAGES = 8
DEFAULT_PER_PART_TIMEOUT = 900.0


class DocumentCheckRunner:
    """Runs the check for one document against one checklist."""

    def __init__(self, model, checklist: Checklist,
                 per_pass_timeout: float = DEFAULT_PER_PART_TIMEOUT):
        self.model = model
        self.checklist = checklist
        self.per_pass_timeout = per_pass_timeout

    def check(self, doc: Document, verbose: bool = False,
              progress_cb=None) -> dict:
        """Returns {results, summary, warnings, meta, document_title}."""
        t0 = time.monotonic()
        raw_results, warnings, timings = self._collect_raw(doc, progress_cb)
        merger = ResultMerger(self.checklist, doc)
        results = merger.finalize(raw_results)
        failures = [w for w in warnings if w.startswith("_failed_pass:")]
        out = {
            "results": [r.to_dict() for r in results],
            "summary": merger.summarize(results),
            "warnings": warnings,
            "document_title": "",
            "_meta": {
                "doc_path": str(doc.path),
                "pages": doc.page_count(),
                "unit": doc.unit,
                "checklist": self.checklist.title,
                "ocr_used": bool(doc.ocr_pages),
                "timings": {**timings, "total": time.monotonic() - t0},
            },
        }
        return out

    # ---- internals -------------------------------------------------------

    def _collect_raw(self, doc: Document, progress_cb):
        raw_results: list[dict] = []
        warnings: list[str] = []
        timings: dict[str, float] = {}
        agent = CheckerAgent(self.model, self.checklist, doc,
                             build_system_prompt(self.checklist.title,
                                                 getattr(self.checklist, "custom_rules", "")),
                             doc_context=f"({doc.page_count()} {doc.unit})")

        if doc.page_count() <= SMALL_DOC_MAX_PAGES:
            raw, dt, err = self._timed_pass(agent, None)
            raw_results.extend(raw)
            timings["single"] = dt
            if err:
                warnings.append(f"Kontrola selhala: {err} — položky zůstávají "
                                "uncertain.")
            return raw_results, warnings, timings

        parts = [r.code for r in self.checklist
                 if "." not in r.code and r.code != "DOKLADY"]
        if any(r.code == "DOKLADY" for r in self.checklist):
            parts.append("DOKLADY")
        raws: list[tuple[list[dict], float, str | None] | None] = [None] * len(parts)

        def run(idx: int, part: str):
            if progress_cb:
                progress_cb("start", part)
            raws[idx] = self._timed_pass(agent, [part])
            if progress_cb:
                progress_cb("done", part)

        with ThreadPoolExecutor(max_workers=len(parts)) as pool:
            futures = {pool.submit(run, i, p): (i, p) for i, p in enumerate(parts)}
            for fut, (idx, part) in futures.items():
                try:
                    fut.result(timeout=self.per_pass_timeout)
                except FuturesTimeoutError:
                    raws[idx] = ([], self.per_pass_timeout,
                                 f"časový limit {self.per_pass_timeout:.0f} s")
                if raws[idx] and raws[idx][2]:
                    warnings.append(f"Kontrola části [{part}] selhala: "
                                    f"{raws[idx][2]} — položky zůstávají uncertain.")
        for raw, dt, _err in [r for r in raws if r]:
            raw_results.extend(raw)
            timings[str(len(timings))] = dt
        return raw_results, warnings, timings

    @staticmethod
    def _timed_pass(agent: CheckerAgent, prefixes: list[str] | None):
        t0 = time.monotonic()
        try:
            raw = agent.run(prefixes)
            return raw.get("results", []), time.monotonic() - t0, None
        except Exception as exc:  # noqa: BLE001 — one failed pass must not kill the run
            return [], time.monotonic() - t0, f"{type(exc).__name__}: {exc}"
