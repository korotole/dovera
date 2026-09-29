"""Markdown + console report rendering for the Annex 13 checker.

Report structure follows the truth-first principle: it states what the
document contains, what the checklist requires, whether they agree, why
they differ (when determinable), what correction may help, and which
items need human confirmation. Discrepancies are never smoothed away.
"""

from __future__ import annotations

import sys

from .annex13_requirements import REQUIREMENTS

_VERDICT_CS = {
    "present": "✅ přítomno",
    "partial": "⚠️ částečně",
    "missing": "❌ chybí",
    "not_applicable": "➖ nevztahuje se",
    "uncertain": "❓ nejisté",
}


def to_markdown(data: dict) -> str:
    meta = data.get("_meta", {})
    is_docx = str(meta.get("pdf_path", "")).lower().endswith(".docx")
    unit = "chunk" if is_docx else "strana"
    dossier = bool(meta.get("dossier"))
    lines = [
        "# Kontrola projektové dokumentace — příloha č. 13 vyhlášky 499/2006 Sb.",
        "",
    ]
    if dossier:
        files = data.get("files", {})
        lines.append(f"- **Složka (dávka):** `{meta.get('pdf_path', '?')}` "
                     f"({meta.get('file_count', '?')} souborů)")
        for name, s in files.items():
            if "error" in s:
                lines.append(f"  - `{name}` — ❌ kontrola selhala")
            else:
                lines.append(
                    f"  - `{name}` — {s.get('present', 0)} ✅ / "
                    f"{s.get('partial', 0)} ⚠️ / {s.get('missing', 0)} ❌ / "
                    f"{s.get('not_applicable', 0)} ➖ / {s.get('uncertain', 0)} ❓")
        lines.append("- **Checklist:** " + meta.get("checklist", "Annex 13"))
        timings = meta.get("timings") or {}
        if timings:
            per = ", ".join(f"[{k}] {v/60:.1f} min" for k, v in sorted(timings.items()))
            lines.append(f"- **Časy kontrol částí:** {per}")
        lines.append("")
        lines.append("*Položky se hodnotí napříč celou dávkou: doloženo, "
                     "když je obsah v alespoň jednom svazku (uvedeno který).*")
    else:
        lines += [
            f"- **Dokument:** `{meta.get('pdf_path', data.get('document_title', '?'))}` "
            f"({meta.get('pages', '?')} {unit}{'ů' if is_docx else ''})",
            f"- **Checklist:** {meta.get('checklist', 'Annex 13')}",
            f"- **Zjištěný titul dokumentu:** {data.get('document_title', '—')}",
            "",
        ]
        timings = meta.get("timings") or {}
        if timings:
            per = ", ".join(f"[{k}] {v/60:.1f} min" for k, v in sorted(timings.items()))
            lines.append(f"- **Časy kontrol částí:** {per}")
            lines.append("")

    results = data.get("results", [])
    by_code = {r["code"]: r for r in results}

    counts = {"present": 0, "partial": 0, "missing": 0,
              "not_applicable": 0, "uncertain": 0}
    for r in results:
        v = r.get("verdict", "uncertain")
        counts[v] = counts.get(v, 0) + 1

    lines.append(
        f"**Souhrn:** {counts['present']} ✅ | {counts['partial']} ⚠️ | "
        f"{counts['missing']} ❌ | {counts['not_applicable']} ➖ | "
        f"{counts['uncertain']} ❓ (z {len(REQUIREMENTS)} položek checklistu)"
    )
    lines.append("")

    # ---------------- Discrepancies ----------------
    diffs = [r for r in results
             if r.get("verdict") in ("partial", "missing", "uncertain")
             and not r.get("verdict") == "not_applicable"]
    lines.append("## Zjištěné rozdíly (dokument vs. příloha č. 13)")
    lines.append("")
    if diffs:
        for r in diffs:
            why = r.get("note", "")
            fix = ""
            lines.append(f"- **[{r['code']}] {r.get('title', '')}** — "
                         f"{_VERDICT_CS.get(r['verdict'], r['verdict'])}"
                         + (f": {why}" if why else ""))
            if fix:
                lines.append(f"  - Návrh opravy: {fix}")
    else:
        lines.append("Žádné rozdíly nenalezeny.")
    lines.append("")

    # ---------------- Requires human confirmation ----------------
    review = [r for r in results if r.get("human_review")]
    lines.append("## Vyžaduje lidské potvrzení")
    lines.append("")
    if review:
        for r in review:
            why = r.get("note", "")
            lines.append(f"- **[{r['code']}] {r.get('title', '')}**"
                         + (f" — {why}" if why else ""))
    else:
        lines.append("Nic — všechny verdikty může agent nést sám.")
    lines.append("")

    # ---------------- Full detail ----------------
    lines.append("## Detail položek")
    lines.append("")
    for req in REQUIREMENTS:
        r = by_code.get(req.code)
        if r is None:
            lines.append(f"### [{req.code}] {req.title}")
            lines.append("")
            lines.append("> ❓ Agent nevydal verdikt — považovat za NEJISTÉ, ne za chybějící.")
            lines.append("")
            continue
        v = r.get("verdict", "uncertain")
        conf = r.get("confidence", "")
        conf_tag = f" (jistota: {conf})" if conf else ""
        lines.append(f"### [{r['code']}] {r.get('title', req.title)} — "
                     f"{_VERDICT_CS.get(v, v)}{conf_tag}")
        if r.get("page"):
            lines.append(f"*{unit} {r['page']}*")
        if r.get("evidence"):
            ev = str(r["evidence"]).strip().replace("\n", " ")
            verified = r.get("evidence_verified")
            mark = "" if verified else " ⚠️ *citát neověřen*"
            lines.append(f"> „{ev}“{mark}")
        if r.get("note"):
            lines.append(f"Poznámka: {r['note']}")
        if r.get("files"):
            per = ", ".join(f"`{n}`: {v}" for n, v in r["files"].items())
            lines.append(f"Svazky: {per}")
        lines.append("")

    return "\n".join(lines)


def print_console_summary(data: dict) -> None:
    counts = {k: 0 for k in ("present", "partial", "missing",
                             "not_applicable", "uncertain")}
    for r in data.get("results", []):
        v = r.get("verdict", "uncertain")
        counts[v] = counts.get(v, 0) + 1
    total = len(data.get("results", []))
    review = sum(1 for r in data.get("results", []) if r.get("human_review"))
    print(
        f"Souhrn: {counts['present']} present / {counts['partial']} partial / "
        f"{counts['missing']} missing / {counts['not_applicable']} n/a / "
        f"{counts['uncertain']} uncertain  (celkem {len(data.get('results', []))}, "
        f"k lidskému posouzení: {review})",
        file=sys.stderr,
    )
