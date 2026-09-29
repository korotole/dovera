"""Dossier mode: check a whole project dossier (folder of PDFs/DOCX).

Real project documentation is usually split across volumes (A — průvodní
zpráva, B — souhrnná technická zpráva, D.* — výkresy). Annex 13 asks about
the documentation *as a whole*, so each checklist item is evaluated across
all files and rolled up:

- ``present``  — verified in at least one file
- ``partial``  — only partial evidence anywhere, nothing complete
- ``uncertain`` — evidence unverifiable / agent uncertain somewhere and no
  file confirms the item
- ``missing``  — no file contains the item (and none was uncertain)

Per-file verdicts stay in the output (``files`` key) — original evidence is
never discarded, and the report shows which volume satisfied what.
"""

from __future__ import annotations

from pathlib import Path

from .annex13_requirements import REQUIREMENTS

_DOC_EXTS = {".pdf", ".docx"}
_RANK = {"present": 3, "partial": 2, "uncertain": 1, "missing": 0,
         "not_applicable": 0}

# roll-up: best evidence wins, but uncertainty keeps human_review on top
_VERDICT_LABEL = {"present": "present", "partial": "partial",
                  "uncertain": "uncertain", "missing": "missing",
                  "not_applicable": "not_applicable"}


def find_documents(folder: str) -> list[Path]:
    """All PDF/DOCX files in folder, sorted by name."""
    root = Path(folder)
    if root.is_file():
        return [root]
    return sorted(p for p in root.iterdir()
                  if p.suffix.lower() in _DOC_EXTS and not p.name.startswith("."))


def run_dossier(folder: str, model, verbose: bool = False,
                per_file_cb=None, per_pass_timeout: float = 900) -> dict:
    """Check every document in *folder*, then merge per checklist item.

    ``per_file_cb(path, result)`` is called after each file (Streamlit
    progress). ``per_pass_timeout`` caps each per-part pass inside a file.
    Returns dict with per-item merged verdicts + per-file detail.
    """
    from .workflow import run_workflow

    docs = find_documents(folder)
    if not docs:
        raise FileNotFoundError(f"no PDF/DOCX files in {folder}")

    per_file: dict[str, dict] = {}
    warnings: list[str] = []
    for path in docs:
        name = path.name
        try:
            out = run_workflow(str(path), model, verbose=verbose,
                               per_pass_timeout=per_pass_timeout)
        except Exception as exc:  # noqa: BLE001 — one bad file must not kill the dossier
            warnings.append(f"Soubor {name}: kontrola selhala ({exc}) — "
                            "položky, které jen tento soubor mohl doložit, "
                            "zůstávají uncertain.")
            per_file[name] = {"error": str(exc), "results": [], "summary": {}}
            if per_file_cb:
                per_file_cb(path, per_file[name])
            continue
        per_file[name] = out
        if out.get("error"):
            warnings.append(f"Soubor {name}: kontrola selhala ({out['error']}) — "
                            "položky, které jen tento soubor mohl doložit, "
                            "zůstávají uncertain.")
        for w in out.get("warnings", []):
            warnings.append(f"[{name}] {w}")
        if per_file_cb:
            per_file_cb(path, out)

    merged: list[dict] = []
    for req in REQUIREMENTS:
        code = req.code
        contributions = []
        for name, out in per_file.items():
            if "error" in out:
                contributions.append((name, "uncertain", None,
                                      "soubor se nepodařilo zkontrolovat"))
                continue
            for r in out.get("results", []):
                if r["code"] == code:
                    contributions.append((name, r["verdict"], r,
                                          r.get("note") or ""))

        verdicts = [(n, v, r) for (n, v, r, _) in contributions]
        best_rank = max((_RANK[v] for _, v, _ in verdicts), default=0)
        best = [x for x in verdicts if _RANK[x[1]] == best_rank]

        if any(v == "uncertain" for _, v, _ in verdicts) and best_rank < 3:
            merged_verdict = "uncertain"
        elif best:
            merged_verdict = best[0][1]
        else:
            merged_verdict = "uncertain"

        # winning evidence: the file with the strongest verdict
        evidence, page, ev_verified, ev_file = "", None, False, None
        ev_toc = False
        for name, v, r in best:
            if r and r.get("evidence"):
                evidence = r["evidence"]
                page = r.get("page")
                ev_verified = bool(r.get("evidence_verified"))
                ev_toc = bool(r.get("evidence_toc_only"))
                ev_file = name
                break

        human_review = any(r.get("human_review") for _, v, r in verdicts
                           if r) or merged_verdict == "uncertain"
        confidences = [r.get("confidence") for _, v, r in verdicts
                       if r and r.get("confidence")]
        conf = "high" if (merged_verdict == "present" and ev_verified
                          and "low" not in confidences) else (
            "low" if merged_verdict == "uncertain" else "medium")

        notes = []
        for name, v, r, note in contributions:
            if note and v in ("partial", "missing", "uncertain"):
                notes.append(f"[{name}: {v}] {note}")
        if len(per_file) > 1 and ev_file:
            label = ("Doloženo souborem" if merged_verdict == "present"
                     else "Nejsilnější důkaz ze svazku")
            notes.append(f"{label}: {ev_file}")

        merged.append({
            "code": code,
            "title": req.title,
            "verdict": merged_verdict,
            "confidence": conf,
            "evidence": evidence,
            "page": page,
            "evidence_verified": ev_verified,
            "evidence_toc_only": ev_toc,
            "human_review": human_review,
            "note": " | ".join(notes),
            "files": {n: v for n, v, _ in verdicts},
        })

    from collections import Counter
    counts = Counter(m["verdict"] for m in merged)
    summary = {k: counts.get(k, 0) for k in
               ("present", "partial", "missing", "not_applicable", "uncertain")}
    out = {
        "results": merged,
        "summary": summary,
        "warnings": warnings,
        "files": {n: (o.get("summary") if "error" not in o
                      else {"error": o["error"]})
                  for n, o in per_file.items()},
        "_meta": {
            "pdf_path": folder,
            "dossier": True,
            "file_count": len(docs),
            "checklist": "V_01_260724_Priloha_c_13_Vyhlaska_499_dokumentace_staveb",
        },
    }
    from .workflow import _persist
    _persist(out)
    return out
