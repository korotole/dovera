"""Minimal web UI: upload, check, table, download. Nothing else."""

from __future__ import annotations

import json
import os
import sys

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dovera.reporting import to_markdown  # noqa: E402

st.set_page_config(page_title="dovera", page_icon="📄", layout="wide")

VERDICT_CS = {
    "present": "✅ přítomno",
    "partial": "⚠️ částečně",
    "missing": "❌ chybí",
    "not_applicable": "➖ nevztahuje se",
    "uncertain": "❓ nejisté",
}


def build_model(backend: str | None = None):
    from dovera.models import build_model as _build

    try:
        return _build(backend=backend)
    except RuntimeError as exc:
        st.error(str(exc))
        st.stop()


st.title("dovera — kontrola dokumentace")

backend = st.sidebar.selectbox(
    "Model", ["auto", "anthropic", "openai", "ollama"],
    help="auto: podle klíčů v prostředí, jinak lokální Ollama")

uploaded = st.file_uploader("PDF / DOCX", type=["pdf", "docx"])

if uploaded is not None and st.button("Spustit kontrolu", type="primary"):
    from dovera.pipeline import Dovers

    os.makedirs("/tmp/dovera_uploads", exist_ok=True)
    path = os.path.join("/tmp/dovera_uploads", uploaded.name)
    with open(path, "wb") as f:
        f.write(uploaded.getvalue())
    with st.spinner("Kontrola probíhá…"):
        st.session_state.last = Dovers(build_model(
            None if backend == "auto" else backend)).check(path)

out = st.session_state.get("last")
if out:
    s = out["summary"]
    st.write(f"**Souhrn:** {s.get('present', 0)} ✅ | {s.get('partial', 0)} ⚠️ | "
             f"{s.get('missing', 0)} ❌ | {s.get('not_applicable', 0)} ➖ | "
             f"{s.get('uncertain', 0)} ❓")

    st.dataframe(pd.DataFrame([{
        "Kód": r["code"],
        "Položka": r.get("title", ""),
        "Verdikt": VERDICT_CS.get(r["verdict"], r["verdict"]),
        "Jistota": r.get("confidence", ""),
        "Důkaz": (r.get("evidence") or "")[:150],
        "Strana": r.get("page") or "",
        "Lidské posouzení": "ano" if r.get("human_review") else "",
    } for r in out["results"]]), use_container_width=True)

    for w in out.get("warnings", []):
        st.warning(w)

    c1, c2 = st.columns(2)
    c1.download_button("Markdown", to_markdown(out),
                       file_name="dovera_report.md", mime="text/markdown")
    c2.download_button("JSON", json.dumps(out, ensure_ascii=False, indent=2),
                       file_name="dovera_results.json", mime="application/json")
