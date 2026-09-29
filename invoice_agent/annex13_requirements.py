"""Annex 13 of Czech Decree 499/2006 Coll. — required structure of
project documentation for construction execution (projektová dokumentace
pro provádění stavby).

Source: https://www.zakonyprolidi.cz/cs/2006-499 (Příloha č. 13).

Each requirement is a checklist node the agent must find evidence for
(or mark as not applicable with a justification).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Requirement:
    """One checkable item of the Annex 13 checklist."""

    code: str          # e.g. "A.1.1.a"
    title: str         # short human-readable name
    description: str   # what the annex requires (paraphrase / key content)
    keywords: list[str] = field(default_factory=list)  # hints for text search
    nta: bool = False  # can be legitimately "not applicable" (non-technical aid)


ANNEX13_TITLE = "V_01_260724_Priloha_c_13_Vyhlaska_499_dokumentace_staveb"

REQUIREMENTS: list[Requirement] = [
    # ---------------- A. Průvodní zpráva ----------------
    Requirement("A", "Průvodní zpráva", "Celá část A - Průvodní zpráva musí být přítomna."),
    Requirement("A.1", "Identifikační údaje", "Identifikace stavby, stavebníka a zpracovatele dokumentace."),
    Requirement(
        "A.1.1", "Údaje o stavbě",
        "Název stavby; místo stavby (adresa, čísla popisná, katastrální území, parcelní čísla pozemků).",
        keywords=["název stavby", "místo stavby", "katastrální území", "parcelní číslo", "číslo popisné"],
    ),
    Requirement(
        "A.1.2", "Údaje o stavebníkovi",
        "Jméno/příjmení a bydliště fyzické osoby, nebo obchodní firma, IČO a místo podnikání/sídla stavebníka.",
        keywords=["stavebník", "IČO", "investor"],
    ),
    Requirement(
        "A.1.3", "Údaje o zpracovateli projektové dokumentace",
        "Zpracovatel dokumentace (jméno/firma, IČO, sídlo); hlavní projektant s autorizačním číslem (ČKA/ČKAIT) a oborem; projektanti jednotlivých částí s autorizací.",
        keywords=["zpracovatel", "projektant", "autorizace", "ČKAIT", "ČKA", "autorizovaný"],
    ),
    Requirement(
        "A.2", "Členění stavby na objekty a technická a technologická zařízení",
        "Stavba rozčleněna na jednotlivé objekty a technická/technologická zařízení.",
        keywords=["členění stavby", "objekty", "technologická zařízení"],
    ),
    Requirement(
        "A.3", "Seznam vstupních podkladů",
        "Informace o rozhodnutích/opatřeních povolujících stavbu (stavební úřad, autorizovaný inspektor, datum, číslo jednací); informace o předchozí dokumentaci; další podklady.",
        keywords=["vstupní podklady", "stavební povolení", "číslo jednací", "územní rozhodnutí", "ohlášení"],
    ),

    # ---------------- B. Souhrnná technická zpráva ----------------
    Requirement("B", "Souhrnná technická zpráva", "Celá část B - souhrnná technická zpráva s přehledem požadavků a)-e)."),
    Requirement(
        "B.0", "Přehledové body souhrnné technické zprávy",
        "Požadavky na dodavatelskou dokumentaci; požadavky na plán BOZP; podmínky realizace v ochranných pásmech; zvláštní podmínky organizace staveniště; ochrana životního prostředí při výstavbě.",
        keywords=["dodavatelská dokumentace", "BOZP", "bezpečnost a ochrana zdraví", "ochranné pásmo", "organizace staveniště", "ochrana životního prostředí"],
    ),
    Requirement(
        "B.1", "Popis území stavby",
        "Charakteristika území a pozemku, soulad s územním rozhodnutím/úPÚN, závazná stanoviska, průzkumy (geologický, hydrogeologický), ochrana území, záplavové/poddolované území, vliv na okolí, asanace/demolice, zábory, územně technické podmínky, věcné a časové vazby, seznam pozemků KN (včetně pásem).",
        keywords=["popis území", "územní rozhodnutí", "geologický průzkum", "záplavové území", "zábory", "územně technické podmínky", "seznam pozemků"],
    ),
    Requirement(
        "B.2", "Celkový popis stavby",
        "Nová stavba/změna stavby + současný stav; účel užívání; trvalá/dočasná; výjimky z technických požadavků; závazná stanoviska; ochrana stavby; parametry (zastavěná plocha, obestavěný prostor, užitná plocha); bilance (médií, dešťová voda, odpady, emise, energetická třída); předpoklady výstavby a etapy; orientační náklady.",
        keywords=["účel užívání", "zastavěná plocha", "obestavěný prostor", "užitná plocha", "energetická náročnost", "orientační náklady", "bilance"],
    ),

    # ---------------- C. Situační výkresy ----------------
    Requirement("C", "Situační výkresy", "Celá část C - situační výkresy."),
    Requirement(
        "C.1", "Situační výkres širších vztahů",
        "Měřítko 1:1000 až 1:50000; napojení na dopravní a technickou infrastrukturu; ochranná a bezpečnostní pásma; hranice dotčeného území.",
        keywords=["situační výkres", "širších vztahů", "1 : 1000", "1:1000", "měřítko"],
    ),
    Requirement(
        "C.2", "Koordinační situační výkres",
        "Měřítko 1:200-1:1000 (rozsáhlé 1:2000/1:5000, památky 1:200); stávající stavby a infrastruktura; hranice pozemků a parcelní čísla; hranice řešeného území; výškopis a polohopis; navržené stavby a odstraňované stavby; ±0,00 a výška terénu, max. výška; komunikace a zpevněné plochy; vegetace; okótované odstupy; technická infrastruktura; pásma; zábory; geotechnické sondy; geodetické údaje a vytyčovací síť; zařízení staveniště s vjezdem; odstupové vzdálenosti, požární technika, zdroje požární vody.",
        keywords=["koordinační situační výkres", "parcelní čísla", "vytyčovací síť", "zařízení staveniště", "požární voda", "geotechnické sondy", "odstupy"],
    ),

    # ---------------- D. Dokumentace objektů ----------------
    Requirement("D", "Dokumentace objektů a technických a technologických zařízení", "Celá část D - dokumentace objektů."),
    Requirement("D.1", "Dokumentace stavebního nebo inženýrského objektu", "Dokumentace jednotlivých objektů v členění D.1.1-D.1.4."),
    Requirement(
        "D.1.1", "Architektonicko-stavební řešení",
        "a) Technická zpráva: účel, funkční náplň, kapacity; architektonické a dispoziční řešení, bezbariérové užívání; provozní řešení; konstrukční řešení; stavební fyzika (tepelná technika, osvětlení, akustika); požární ochrana konstrukcí; jakost materiálů; dokumentace zhotovitele; kontroly zakrývaných konstrukcí; výpis norem. b) Výkresová část: stavební jáma, půdorysy podlaží s kótami a popisem místností, řezy, střecha/krov, pohledy fasád s barevností. c) Dokumenty podrobností: skladby konstrukcí, seznamy částí, rozhodující detaily, detaily bezbariérových opatření.",
        keywords=["architektonick", "dispoziční řešení", "stavební fyzika", "půdorysy", "fasád", "skladby konstrukcí", "bezbariérov"],
    ),
    Requirement(
        "D.1.2", "Stavebně konstrukční řešení",
        "a) Technická zpráva: nosný systém, průřezové rozměry, zatížení, jakost materiálů, zajištění stavební jámy, kontroly zakrývaných konstrukcí, změny stávající stavby, dokumentace zhotovitele, seznam podkladů. b) Podrobný statický výpočet: průvodní zpráva, podklady, statické schéma, zatížení, výpočetní modely, návrh a posouzení prvků, základy, detaily, postup výroby. c) Výkresová část: půdorysy nosných konstrukcí 1:50 (vyj. 1:100), řezy, detaily 1:20/1:10/1:5, prefabrikáty, vyztužení.",
        keywords=["statický výpočet", "nosný systém", "zatížení", "vyztužení", "stavební jáma"],
    ),
    Requirement(
        "D.1.3", "Požárně bezpečnostní řešení",
        "Revize a doplnění požárně bezpečnostního řešení z předchozího stupně dokumentace, včetně vyznačení změn.",
        keywords=["požárně bezpečnostní", "požární bezpečnost", "PBS", "požární řešení"],
    ),
    Requirement(
        "D.1.4", "Technika prostředí staveb",
        "Dokumentace jednotlivých profesí (zdravotně technické instalace, plyn, vzduchotechnika, vytápění, chlazení, měření a regulace, silnoproudá elektrotechnika včetně ochrany před bleskem, elektronické komunikace). a) Technická zpráva: parametry, bilance médií, řešení instalace, připojení na infrastrukturu, bezpečný provoz, požární opatření, hluk, životní prostředí, výpočty, doklady pro užívání, normy. b) Výkresová část: situace s přípojkami, profily přípojek, umístění strojů, trasy potrubí a kabelů, axonometrie, schémata. c) Seznam strojů a zařízení a technické specifikace.",
        keywords=["vytápění", "vzduchotechnika", "elektro", "měření a regulace", "plynové", "ochrana před bleskem", "technika prostředí"],
    ),
    Requirement(
        "D.2", "Dokumentace technických a technologických zařízení",
        "Dokumentace technologických zařízení po provozních celcích: a) Technická zpráva (výrobní program, technologie, potřeby energií a médií, doprava, doklady, normy); b) Výkresová část (umístění zařízení, schémata rozvodů, půdorysy tras, technologická schémata); c) Seznam strojů a zařízení a technické specifikace.",
        keywords=["technologické zařízení", "výrobní program", "technologická schémata", "provozní celky"],
    ),

    # ---------------- Dokladová část ----------------
    Requirement(
        "DOKLADY", "Dokladová část",
        "Doklady o splnění požadavků podle jiných právních předpisů: 1. vytyčovací výkresy objektů; 2. projekt zpracovaný báňským projektantem (pokud se týká).",
        keywords=["dokladová část", "vytyčovací výkres", "báňský projektant"],
    ),
]


def section(code: str) -> list[Requirement]:
    """Return requirements whose code starts with given prefix."""
    return [r for r in REQUIREMENTS if r.code == code or r.code.startswith(code + ".")]
