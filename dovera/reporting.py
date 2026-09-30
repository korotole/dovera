"""Markdown + console report rendering, checklist-agnostic."""

from __future__ import annotations

import sys

_VERDICT_CS = {
    "present": "✅ přítomno",
    "partial": "⚠️ částečně",
    "missing": "❌ chybí",
    "not_applicable": "➖ nevztahuje se",
    "uncertain": "❓ nejisté",
}


def to_markdown(out: dict) -> str:
    meta = out.get("_meta", {})
    dossier = bool(meta.get("dossier"))
    lines = [f"# Kontrola dokumentace — {meta.get('checklist', 'checklist')}", ""]

    if dossier:
        lines.append(f"- **Složka (dávka):** `{meta.get('doc_path', '?')}` "
                     f"({meta.get('file_count', '?')} souborů)")
        for name, s in out.get("files", {}).items():
            if "error" in s:
                lines.append(f"  - `{name}` — ❌ kontrola selhala")
            else:
                lines.append(f"  - `{name}` — {_summary_line(s)}")
        lines.append("")
    else:
        lines.append(f"- **Dokument:** `{meta.get('doc_path', '?')}` "
                     f"({meta.get('pages', '?')} {meta.get('unit', 'stran')})")
        if title := out.get("document_title"):
            lines.append(f"- **Zjištěný titul:** {title}")
        lines.append("")

    timings = meta.get("timings") or {}
    if timings:
        per = ", ".join(f"[{k}] {v / 60:.1f} min" if v > 90 else f"[{k}] {v:.0f} s"
                        for k, v in sorted(timings.items()))
        lines.append(f"- **Časy:** {per}")
        lines.append("")

    s = out.get("summary", {})
    lines.append(f"**Souhrn:** {s.get('present', 0)} ✅ | {s.get('partial', 0)} ⚠️ | "
                 f"{s.get('missing', 0)} ❌ | {s.get('not_applicable', 0)} ➖ | "
                 f"{s.get('uncertain', 0)} ❓")
    lines.append("")

    lines += _discrepancies(out)
    lines += _human_review(out)
    lines += _detail(out)
    return "\n".join(lines)


def _summary_line(s: dict) -> str:
    return (f"{s.get('present', 0)} ✅ / {s.get('partial', 0)} ⚠️ / "
            f"{s.get('missing', 0)} ❌ / {s.get('not_applicable', 0)} ➖ / "
            f"{s.get('uncertain', 0)} ❓")


def _discrepancies(out: dict) -> list[str]:
    diffs = [r for r in out["results"]
             if r["verdict"] in ("partial", "missing", "uncertain")]
    lines = ["## Zjištěné rozdíly", ""]
    if not diffs:
        return lines + ["Žádné rozdíly nenalezeny.", ""]
    for r in diffs:
        line = (f"- **[{r['code']}] {r.get('title', '')}** — "
                f"{_VERDICT_CS.get(r['verdict'], r['verdict'])}")
        if r.get("note"):
            line += f": {r['note']}"
        lines.append(line)
    lines.append("")
    return lines


def _human_review(out: dict) -> list[str]:
    review = [r for r in out["results"] if r.get("human_review")]
    lines = ["## Vyžaduje lidské potvrzení", ""]
    if not review:
        return lines + ["Nic — verdikty jsou podepřeny ověřenými citáty.", ""]
    for r in review:
        line = f"- **[{r['code']}] {r.get('title', '')}**"
        if r.get("note"):
            line += f" — {r['note']}"
        lines.append(line)
    lines.append("")
    return lines


def _detail(out: dict) -> list[str]:
    unit = out.get("_meta", {}).get("unit", "strana").replace("ů", "").replace("y", "a")
    lines = ["## Detail položek", ""]
    for r in out["results"]:
        conf = r.get("confidence", "")
        conf_tag = f" (jistota: {conf})" if conf else ""
        lines.append(f"### [{r['code']}] {r.get('title', '')} — "
                     f"{_VERDICT_CS.get(r['verdict'], r['verdict'])}{conf_tag}")
        if r.get("page"):
            lines.append(f"*{unit} {r['page']}*")
        if r.get("evidence"):
            mark = "" if r.get("evidence_verified") else " ⚠️ *citát neověřen*"
            lines.append(f"> „{str(r['evidence']).strip()}“{mark}")
        if r.get("note"):
            lines.append(f"Poznámka: {r['note']}")
        if r.get("files"):
            per = ", ".join(f"`{n}`: {v}" for n, v in r["files"].items())
            lines.append(f"Svazky: {per}")
        lines.append("")
    return lines


def print_console_summary(out: dict) -> None:
    s = out.get("summary", {})
    review = sum(1 for r in out.get("results", []) if r.get("human_review"))
    print(f"Souhrn: {s.get('present', 0)} present / {s.get('partial', 0)} partial / "
          f"{s.get('missing', 0)} missing / {s.get('not_applicable', 0)} n/a / "
          f"{s.get('uncertain', 0)} uncertain (k lidskému posouzení: {review})",
          file=sys.stderr)
