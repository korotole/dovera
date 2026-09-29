"""LangChain agent that checks a construction-project PDF against
Annex 13 of Czech Decree 499/2006 Coll.

Design:
  - checklist lives in annex13_requirements.py (data, not prompts)
  - agent gets 3 tools: get_requirements, search_pdf, read_page
  - per requirement the agent searches for evidence, then emits a verdict
    (present / partial / missing / not_applicable) with a quoted excerpt
  - final output: structured JSON + Markdown report

The agent is a single ReAct-style loop (LangChain create_agent) rather than
a fixed pipeline: requirements differ per document type, and the agent needs
freedom to search the PDF in whatever order evidence appears.
"""

from __future__ import annotations

import json
import re
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool

from .annex13_requirements import ANNEX13_TITLE, REQUIREMENTS, Requirement
from .pdf_tools import _normalize_text, load_pdf, search_pages

# ---------------------------------------------------------------------------
# Tools (bound to one PDF per run via closure)
# ---------------------------------------------------------------------------


def make_tools(pdf_path: str):
    pdf = load_pdf(pdf_path)
    return _make_tools_for(pdf), pdf


def _make_tools_for(pdf):

    @tool
    def get_requirements(code_prefix: str = "") -> str:
        """Get Annex 13 checklist items. Pass empty string for all items,
        or a code prefix like 'A', 'A.1', 'B.2', 'D.1.3' to filter.
        Returns code, title and description for each requirement."""
        reqs = [r for r in REQUIREMENTS
                if not code_prefix or r.code == code_prefix
                or r.code.startswith(code_prefix + ".")]
        if not reqs:
            return f"No requirements found for prefix '{code_prefix}'."
        return "\n".join(
            f"[{r.code}] {r.title}\n  {r.description}" for r in reqs
        )

    @tool
    def search_pdf(query: str) -> str:
        """Search the PDF text for a phrase (Czech, diacritics-insensitive).
        Returns up to 10 hits as 'page N: ...excerpt...' lines.
        Hits marked [TOC] are from the table of contents — they show only
        that a headline exists, NOT that the content is there. Never use a
        TOC hit alone as evidence for 'present'.
        Use short distinctive phrases, e.g. 'katastrální území',
        'statický výpočet', 'požárně bezpečnostní'."""
        hits = search_pages(pdf, query)
        if not hits:
            return f"No hits for '{query}'. Try different wording."
        return "\n".join(
            f"page {h['page']}" + (" [TOC]" if h.get("toc") else "") +
            f": {h['excerpt']}"
            for h in hits
        )

    @tool
    def read_page(page_number: int) -> str:
        """Read full text of one PDF page (1-based). Use after a search hit
        or to inspect a page that looks like it contains a required section."""
        if page_number < 1 or page_number > pdf.page_count():
            return f"Invalid page {page_number}. Document has {pdf.page_count()} pages."
        text = pdf.pages[page_number - 1]
        if not text:
            return (f"Page {page_number} has no extractable text "
                    "(scan/image page? content may exist in a drawing — "
                    "verdict must be uncertain with human_review).")
        return text

    return [get_requirements, search_pdf, read_page]


SYSTEM_PROMPT = """Jsi kontrolor projektové dokumentace stavby podle přílohy č. 13 vyhlášky č. 499/2006 Sb.

Úkol: ZJISTIT a DOKLADNĚ POPSAT, co dokument obsahuje a co z kontrolního seznamu
(příloha č. 13) pokrývá — NE "vydat čistý výsledek". Nesmíš skrývat zjištěné
rozdíly, přetvářet nejistotu na jistotu ani vymýšlet chybějící informace.

Postup:
1. Zavolej get_requirements s prázdným prefixem a získej celý kontrolní seznam.
2. Pro KAŽDOU položku seznamu:
   - Hledej důkazy pomocí search_pdf s krátkými charakteristickými frázemi
     (z názvů položek a keywords; zkus 2-4 varianty, pokud nic nenajdeš).
   - Když najdeš kandidate, ověř kontext pomocí read_page.
3. Pro každou položku vydej verdikt:
   - "present": obsah je v dokumentu zcela jasně přítomen (máš doslovný důkaz)
   - "partial": přítomen částečně (uveď přesně, co přítomno a co chybí)
   - "missing": po důkladném hledání nenalezen žádný důkaz
   - "not_applicable": položka se na tuto stavbu/dokument nevztahuje (uveď proč,
     s oporou v textu dokumentu)
   - "uncertain": nalezl jsi nepřímé/nejednoznačné indicie a NEJSI si jistý —
     POUŽIJ místo odhadu. Nejistota patří do verdiktu "uncertain", ne do "present".
4. Ke každému verdiktu přidej:
   - "evidence": doslovný citát z dokumentu (max ~200 znaků); u "missing" prázdný
   - "page": číslo strany (resp. chunku) s důkazem
   - "confidence": "high" (jasný doslovný důkaz) | "medium" (důkaz s mírnou
     nejistotou kontextu) | "low" (indicie pouze)
   - "human_review": true jen když verdikt nemůžeš zodpovědně vydat sám
     (nejednoznačný text, možná errata, nutná znalost celého svazku dokumentace)
5. U "partial"/"missing"/"uncertain" uveď v "note" PRŮČINU rozdílu, pokud je
   z dokumentu zjistitelný (např. "tento svazek obsahuje jen část B", "zmínka
   pouze v obsahu, kapitola chybí"), a NÁVRH OPRAVY, je-li možný (např.
   "doplnit kapitolu s bilancí médií"). Nezjistitelný důvod napiš explicitně:
   "důvod rozdílu nelze z dokumentu určit".

Pravidla:
- Verdikt vždy opírej o konkrétní text z dokumentu, ne o domněnky.
- Citát musí být doslovný výňatek z dokumentu. Nikdy si nevymýšlej obsah.
- not_applicable jen s oprávněným důvodem (např. stavba nemá technologická
  zařízení u D.2 — ale jen pokud dokument to explicitně podporuje).
- Pokud je dokument zjevně jen JEDEN SVAZEK větší dokumentace (např. pouze
  "Souhrnná technická zpráva" = část B), položky ostatních částí (A, C, D,
  doklady) označ "not_applicable" s poznámkou "náleží do jiného svazku
  dokumentace" místo "missing".
- Položka "DOKLADY" (Dokladová část): pokud dokument je projektová dokumentace
  a vyjmenovává její přiloženou dokladovou část (např. oddíl "Dokladová část:
  Obsahuje: 1. Vytyčovací výkresy..."), je to "present". Skutečné doklady bývají
  v samostatném svazku; jejich absence v tomto PDF není důvod k "partial".
  POZOR: pouhá zmínka o dokladech v korespondenci/reklamaci ("zasíláme doklad...")
  dokladovou část NENÍ — to je "missing".
- Rozhodující je, zda dokument danou náležitost SKUTEČNĚ obsahuje/řeší,
  ne jen zda ji náhodou jmenuje v jiném kontextu (reklamace, korespondence,
  seznamy příloh bez vlastního obsahu).
- Když hledání nic ne najde, NENÍ to důkaz neexistence — zvaž "uncertain"
  s human_review:true, pokud mohl být obsah ve výkresech, obrázcích, tabulkách
  nebo jiném svazku, které tento soubor nezachycuje.

Finální odpověď: POUZE JSON (žádný jiný text) ve formátu:
{
  "document_title": "<název/název stavby z dokumentu>",
  "results": [
    {"code": "A.1.1", "title": "Údaje o stavbě", "verdict": "present",
     "evidence": "<doslovný citát>", "page": 3, "confidence": "high",
     "human_review": false, "note": "<důvod rozdílu / co chybí / návrh opravy>"}
  ],
  "summary": {"present": N, "partial": N, "missing": N, "not_applicable": N, "uncertain": N}
}"""


def _extract_json(text: str) -> dict[str, Any]:
    """Pull the first JSON object out of an LLM reply."""
    text = text.strip()
    # strip markdown fences if present
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON object in reply: {text[:200]!r}")
    return json.loads(text[start:end + 1])


def _normalize_verdict(raw: Any) -> str:
    v = str(raw).strip().lower()
    if v in ("present", "partial", "not_applicable", "uncertain"):
        return v
    return "missing"


def _squash(text: str) -> str:
    """Collapse all whitespace runs to single spaces (quote-vs-page matching)."""
    return re.sub(r"\s+", " ", text).strip()


def _verify_results(data: dict[str, Any], pdf) -> dict[str, Any]:
    """Post-process raw agent JSON into a trustworthy result.

    - normalizes verdicts (unknown string -> uncertain + human_review)
    - fills in skipped checklist codes as uncertain (never silently absent)
    - checks quoted evidence against the claimed page; unverifiable quotes
      are flagged and the verdict downgraded to uncertain + human_review —
      never silently kept, never silently flipped to missing
    - never trusts LLM-computed summary counts
    """
    from collections import Counter

    by_code = {}
    for r in data.get("results", []):
        code = str(r.get("code", "")).strip()
        if not code:
            continue
        if code not in {req.code for req in REQUIREMENTS}:
            continue  # hallucinated checklist code — drop
        raw_verdict = str(r.get("verdict", "")).strip().lower()
        r["verdict"] = _normalize_verdict(r.get("verdict"))
        if raw_verdict not in ("present", "partial", "missing",
                               "not_applicable", "uncertain"):
            # unknown verdict string: preserve as uncertainty, not certainty
            r["verdict"] = "uncertain"
            r["human_review"] = True
            r["note"] = (f"Neznámý verdikt '{raw_verdict}' od agenta — "
                         "vyžaduje lidské posouzení. " + str(r.get("note", ""))).strip()
        # confidence + human_review defaults
        if r.get("confidence") not in ("high", "medium", "low"):
            r["confidence"] = "medium" if r["verdict"] in ("present", "partial") else "low"
        r["human_review"] = bool(r.get("human_review", False))
        # evidence must exist on the claimed page (normalized comparison);
        # whitespace-insensitive: quotes may span line breaks
        ev = str(r.get("evidence") or "").strip()
        page = r.get("page")
        if r["verdict"] in ("present", "partial") and ev:
            verified = False
            on_toc = isinstance(page, int) and page in pdf.toc_pages
            if isinstance(page, int) and 1 <= page <= pdf.page_count():
                page_text = _squash(_normalize_text(pdf.pages[page - 1]))
                needle = _squash(_normalize_text(ev))
                # full quote first, then progressively shorter prefixes
                if len(needle) >= 15 and needle in page_text:
                    verified = True
                else:
                    for size in (60, 40, 25):
                        if len(needle) >= size and needle[:size] in page_text:
                            verified = True
                            break
                if not verified:
                    # LLM may join separate lines with "/" or "...": quote is
                    # verified when every meaningful fragment appears on the page
                    frags = [f.strip(" .,/…") for f in re.split(r"/|\.\.\.|…", needle)]
                    frags = [f for f in frags if len(f) >= 12]
                    if frags and all(f in page_text for f in frags):
                        verified = True
            if verified and on_toc:
                # evidence exists but is only a TOC entry — headline, not content
                r["evidence_verified"] = False
                r["evidence_toc_only"] = True
                r["verdict"] = "uncertain"
                r["human_review"] = True
                r["note"] = ("Citát pochází z OBSAHU (table of contents) — dokazuje "
                             "jen existenci nadpisu, ne skutečného obsahu. Verdikt "
                             "degradován na uncertain. " + str(r.get("note", ""))).strip()
                by_code[code] = r
                continue
            r["evidence_verified"] = verified
            r["evidence_verified"] = verified
            if not verified:
                # NEVER pass unverified evidence as certainty — downgrade
                r["verdict"] = "uncertain"
                r["human_review"] = True
                r["note"] = (
                    "UVEDENÝ CITÁT SE NEPODAŘILO NAJÍT na uvedené straně "
                    f"({page}) — verdikt degradován na uncertain. Původní "
                    f"verdikt: {r['verdict'] if r['verdict'] != 'uncertain' else 'present/partial'}. "
                    + str(r.get("note", ""))).strip()
                if verbose_flag[0]:
                    print(f"[verify] evidence NOT found on page {page} for {code} -> uncertain")
        by_code[code] = r

    # any checklist item the agent skipped -> explicit uncertain entry
    # (never silently absent, never assumed missing)
    for req in REQUIREMENTS:
        if req.code not in by_code:
            by_code[req.code] = {
                "code": req.code, "title": req.title, "verdict": "uncertain",
                "evidence": "", "page": None, "confidence": "low",
                "human_review": True,
                "note": "Agent nevydal verdikt (položka chyběla v odpovědi) — "
                        "vyžaduje lidské posouzení.",
            }

    _roll_up_parents(by_code)
    data["results"] = [by_code[req.code] for req in REQUIREMENTS]

    counts = Counter(r["verdict"] for r in data["results"])
    data["summary"] = {k: counts.get(k, 0)
                       for k in ("present", "partial", "missing",
                                 "not_applicable", "uncertain")}
    return data


def _roll_up_parents(by_code: dict[str, dict]) -> None:
    """Recompute parent-section verdicts from children (deterministic).

    Parent = code without children in checklist data stays as-is. A parent with
    children gets: all children present -> present; any missing -> worst of
    (partial if some child present/partial, else missing); n/a only when every
    child is n/a. Leaf verdicts from the LLM are never modified.
    """
    children_of = {}
    for req in REQUIREMENTS:
        if "." in req.code:
            parent = req.code.rsplit(".", 1)[0]
            children_of.setdefault(parent, []).append(req.code)

    for parent, child_codes in children_of.items():
        if parent not in by_code:
            continue
        kids = [by_code[c] for c in child_codes if c in by_code]
        if not kids:
            continue
        verdicts = [k["verdict"] for k in kids]
        if all(v == "not_applicable" for v in verdicts):
            rolled = "not_applicable"
        elif all(v == "present" for v in verdicts):
            rolled = "present"
        elif all(v == "missing" for v in verdicts):
            rolled = "missing"
        elif any(v == "uncertain" for v in verdicts):
            # any uncertainty propagates up — never smoothed into a cleaner verdict
            rolled = "uncertain"
        else:
            rolled = "partial"
        p = by_code[parent]
        if p["verdict"] != rolled:
            p["note"] = (p.get("note", "") +
                         f" [Verdict části přepočítán z podpoložek: {rolled}.]").strip()
        p["verdict"] = rolled
        # parent inherits review flag when any child needs it
        if any(k.get("human_review") for k in kids):
            p["human_review"] = True
        # parent confidence = weakest child confidence
        rank = {"high": 0, "medium": 1, "low": 2}
        p["confidence"] = max((k.get("confidence", "low") for k in kids),
                              key=lambda c: rank[c])


# one-element list = mutable flag set by check_document (module-level default)
verbose_flag = [False]


def check_document(pdf_path: str, model: Any, verbose: bool = False,
                   max_retries: int = 2) -> dict[str, Any]:
    """Run the Annex 13 compliance check on a PDF. Returns the parsed JSON verdict.

    Retries once on invalid JSON reply. On recursion-limit (agent ran out of
    turns before answering), sends one follow-up asking for the JSON now,
    based on what it already found.
    """
    verbose_flag[0] = verbose
    tools, pdf = make_tools(pdf_path)
    agent = create_agent(model, tools, system_prompt=SYSTEM_PROMPT)

    doc_kind = "chunk" if pdf_path.lower().endswith(".docx") else "stran"
    msg = (
        f"Zkontroluj dokument '{pdf_path}' ({pdf.page_count()} {doc_kind}) "
        f"podle přílohy č. 13 vyhlášky 499/2006 Sb. "
        f"Vrať finální JSON s verdikty pro všechny položky kontrolního seznamu."
    )
    state = {"messages": [HumanMessage(content=msg)]}
    config = {"recursion_limit": 120}

    last_text = ""
    for attempt in range(max_retries + 1):
        try:
            result = agent.invoke(state, config=config)
            state = result  # keep context for retry
        except Exception as exc:  # noqa: BLE001 — includes GraphRecursionError
            if "recursion" in str(exc).lower() and attempt < max_retries:
                if verbose:
                    print("[agent] recursion limit hit, asking for final JSON")
                state["messages"].append(HumanMessage(
                    content=("Dosažen limit kroků. Na základě toho, co už víš, "
                             "PROMÍTNĚ kontroly jen pro položky, ke kterým máš "
                             "důkazy, a VRAŤ teď finální JSON (zbývající položky "
                             "jako \"missing\"). Žádný jiný text.")))
                continue
            raise

        final_text = result["messages"][-1].content
        if isinstance(final_text, list):  # some providers return content blocks
            final_text = "".join(
                b.get("text", "") for b in final_text if isinstance(b, dict)
            )
        last_text = final_text
        try:
            data = _extract_json(final_text)
            break
        except (ValueError, json.JSONDecodeError) as exc:
            if attempt >= max_retries:
                raise
            if verbose:
                print(f"[agent] invalid JSON (attempt {attempt + 1}): {exc}")
            state["messages"].append(HumanMessage(
                content=("Tvoje odpověď nebyla platný JSON. Vrať POUZE jeden "
                         "platný JSON objekt bez komentářů a bez markdown "
                         "fencing, se všemi položkami kontrolního seznamu.")))

    data = _verify_results(data, pdf)
    data["_meta"] = {
        "pdf_path": pdf_path,
        "pages": pdf.page_count(),
        "checklist": ANNEX13_TITLE,
    }
    return data


# ---------------------------------------------------------------------------
# Workflow-facing helpers (used by workflow.py)
# ---------------------------------------------------------------------------


def build_agent(model: Any, system_prompt: str, doc_path: str | None = None,
                pdf=None):
    """Build a ReAct agent bound to one document's tools."""
    from langchain.agents import create_agent

    if pdf is not None:
        tools = _make_tools_for(pdf)
    else:
        tools, _pdf = make_tools(doc_path)
    return create_agent(model, tools, system_prompt=system_prompt)


def run_agent_turn(agent, pdf, prefixes: list[str] | None, verbose: bool = False,
                   doc_path: str = "", max_retries: int = 2) -> dict[str, Any]:
    """One full agent conversation: check `prefixes` slice of the checklist
    (None = all items), return raw parsed JSON (no post-processing)."""
    scope = ""
    if prefixes:
        scope = ("Zkontroluj POUZE položky s kódy začínajícími na: "
                 f"{', '.join(prefixes)}. Jiné položky NEVypisuj.")
    doc_kind = "chunk" if doc_path.lower().endswith(".docx") else "stran"
    msg = (
        f"Zkontroluj dokument '{doc_path}' ({pdf.page_count()} {doc_kind}) "
        f"podle přílohy č. 13 vyhlášky 499/2006 Sb. {scope} "
        f"Vrať finální JSON s verdikty pro příslušné položky kontrolního seznamu."
    )
    state = {"messages": [HumanMessage(content=msg)]}
    config = {"recursion_limit": 120}

    for attempt in range(max_retries + 1):
        try:
            result = agent.invoke(state, config=config)
            state = result
        except Exception as exc:  # noqa: BLE001 — includes GraphRecursionError
            if "recursion" in str(exc).lower() and attempt < max_retries:
                if verbose:
                    print("[agent] recursion limit hit, asking for final JSON")
                state["messages"].append(HumanMessage(
                    content=("Dosažen limit kroků. Na základě toho, co už víš, "
                             "vyzvy verdikty jen pro položky, ke kterým máš "
                             "důkazy, a VRAŤ teď finální JSON (ostatní položky "
                             "vědomě VYPUSŤ — doplní se jako uncertain). "
                             "Žádný jiný text.")))
                continue
            raise

        final_text = result["messages"][-1].content
        if isinstance(final_text, list):
            final_text = "".join(
                b.get("text", "") for b in final_text if isinstance(b, dict)
            )
        try:
            return _extract_json(final_text)
        except (ValueError, json.JSONDecodeError) as exc:
            if attempt >= max_retries:
                raise
            if verbose:
                print(f"[agent] invalid JSON (attempt {attempt + 1}): {exc}")
            state["messages"].append(HumanMessage(
                content=("Tvoje odpověď nebyla platný JSON. Vrať POUZE jeden "
                         "platný JSON objekt bez komentářů a bez markdown "
                         "fencing, s položkami kontrolního seznamu.")))
    raise ValueError("agent did not produce valid JSON in time")
