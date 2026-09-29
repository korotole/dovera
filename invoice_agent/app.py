"""Minimal Streamlit GUI for the Annex 13 checker.

One input (file or folder path), one button, one table, downloads.
Run: uv run streamlit run invoice_agent/app.py
"""

from __future__ import annotations

import json
import os
import sys

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from invoice_agent.report import to_markdown  # noqa: E402

st.set_page_config(page_title="Kontrola PD — příloha 13", page_icon="🏗️",
                   layout="wide")

_VERDICT_CS = {
    "present": "✅ přítomno",
    "partial": "⚠️ částečně",
    "missing": "❌ chybí",
    "not_applicable": "➖ nevztahuje se",
    "uncertain": "❓ nejisté",
}


def build_model():
    from langchain_anthropic import ChatAnthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    if not api_key:
        st.error("Chybí ANTHROPIC_API_KEY (nebo ANTHROPIC_AUTH_TOKEN) v prostředí.")
        st.stop()
    return ChatAnthropic(
        model=os.environ.get("AGENT_MODEL", "claude-sonnet-5"),
        max_tokens=8000,
        timeout=600,
        api_key=api_key,
        base_url=os.environ.get("ANTHROPIC_BASE_URL") or None,
    )


st.title("Kontrola projektové dokumentace")
st.caption("dle přílohy č. 13 vyhlášky č. 499/2006 Sb.")

uploaded = st.file_uploader("PDF / DOCX", type=["pdf", "docx"])

if uploaded is not None and st.button("Spustit kontrolu", type="primary"):
    model = build_model()
    from invoice_agent.workflow import run_workflow

    path = os.path.join("/tmp/annex13_uploads", uploaded.name)
    os.makedirs("/tmp/annex13_uploads", exist_ok=True)
    with open(path, "wb") as f:
        f.write(uploaded.getvalue())

    with st.spinner("Kontrola probíhá…"):
        out = run_workflow(path, model)
    st.session_state.last = out

out = st.session_state.get("last")
if out:
    s = out["summary"]
    st.write(f"**Souhrn:** {s.get('present', 0)} ✅ | {s.get('partial', 0)} ⚠️ | "
             f"{s.get('missing', 0)} ❌ | {s.get('not_applicable', 0)} ➖ | "
             f"{s.get('uncertain', 0)} ❓")

    rows = [{
        "Kód": r["code"],
        "Položka": r.get("title", ""),
        "Verdikt": _VERDICT_CS.get(r["verdict"], r["verdict"]),
        "Jistota": r.get("confidence", ""),
        "Důkaz": (r.get("evidence", "") or "")[:150],
        "Strana/chunk": r.get("page") or "",
        "Lidské posouzení": "ano" if r.get("human_review") else "",
    } for r in out["results"]]
    st.dataframe(pd.DataFrame(rows), use_container_width=True)

    for w in out.get("warnings", []):
        st.warning(w)

    c1, c2 = st.columns(2)
    c1.download_button("Markdown report", to_markdown(out),
                       file_name="kontrola_priloha13.md", mime="text/markdown")
    c2.download_button("JSON", json.dumps(out, ensure_ascii=False, indent=2),
                       file_name="kontrola_priloha13.json", mime="application/json")
    if out.get("_meta", {}).get("pdf_path"):
        st.caption(f"uloženo do GraphQL store (je-li spuštěn): "
                   f"{out['_meta']['pdf_path']}")
