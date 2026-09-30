"""Annex 13 (Příloha č. 13) of Czech Decree 499/2006 Sb. — required structure
of project documentation for construction execution.

Source: https://www.zakonyprolidi.cz/cs/2006-499 (Příloha č. 13).
"""

from __future__ import annotations

from dovera.checklists.base import Checklist, Requirement

TITLE = "V_01_260724_Priloha_c_13_Vyhlaska_499_dokumentace_staveb"

_R = Requirement


class Annex13Checklist(Checklist):

    title = TITLE

    def __init__(self):
        super().__init__([
            # ---- A. Průvodní zpráva
            _R("A", "Průvodní zpráva",
               "Celá část A - Průvodní zpráva musí být přítomna."),
            _R("A.1", "Identifikační údaje",
               "Identifikace stavby, stavebníka a zpracovatele dokumentace."),
            _R("A.1.1", "Údaje o stavbě",
               "Název stavby; místo stavby (adresa, čísla popisná, katastrální "
               "území, parcelní čísla pozemků).",
               ("název stavby", "místo stavby", "katastrální území",
                "parcelní číslo", "číslo popisné")),
            _R("A.1.2", "Údaje o stavebníkovi",
               "Jméno/příjmení a bydliště fyzické osoby, nebo obchodní firma, "
               "IČO a místo podnikání/sídla stavebníka.",
               ("stavebník", "IČO", "investor")),
            _R("A.1.3", "Údaje o zpracovateli projektové dokumentace",
               "Zpracovatel dokumentace (jméno/firma, IČO, sídlo); hlavní "
               "projektant s autorizačním číslem (ČKA/ČKAIT) a oborem; "
               "projektanti jednotlivých částí s autorizací.",
               ("zpracovatel", "projektant", "autorizace", "ČKAIT", "ČKA",
                "autorizovaný")),
            _R("A.2", "Členění stavby na objekty a technická a technologická "
               "zařízení",
               "Stavba rozčleněna na jednotlivé objekty a technická/"
               "technologická zařízení.",
               ("členění stavby", "objekty", "technologická zařízení")),
            _R("A.3", "Seznam vstupních podkladů",
               "Informace o rozhodnutích/opatřeních povolujících stavbu "
               "(stavební úřad, autorizovaný inspektor, datum, číslo jednací); "
               "informace o předchozí dokumentaci; další podklady.",
               ("vstupní podklady", "stavební povolení", "číslo jednací",
                "územní rozhodnutí", "ohlášení")),

            # ---------------- B. Souhrnná technická zpráva ----------------
            _R("B", "Souhrnná technická zpráva",
               "Celá část B - souhrnná technická zpráva s přehledem "
               "požadavků a)-e)."),
            _R("B.0", "Přehledové body souhrnné technické zprávy",
               "Souhrn požadavků a)-e): dodavatelská dokumentace, plán BOZP, "
               "ochrana životního prostředí, zvláštní podmínky organizace "
               "staveniště, podmínky realizace v ochranných pásmech.",
               ("požadavky", "BOZP", "ochrana životního prostředí",
                "zvláštní podmínky", "ochranná pásma")),
            _R("B.1", "Popis území stavby",
               "Charakteristika území a stavebního pozemku; soulad s územním "
               "rozhodnutím/stanovisky ochranných pásem; vlivy stavby na území.",
               ("charakteristika území", "územní rozhodnutí", "ochranná pásma",
                "vlivy stavby")),
            _R("B.2", "Celkový popis stavby",
               "Parametry a bilance: zastavěná plocha, obestavěný prostor, "
               "užitná plocha, počet podlaží/funkčních jednotek; potřeby a "
               "spotřeby médií (voda, plyn, el. energie, teplo); předpokládané "
               "termíny realizace a náklady.",
               ("zastavěná plocha", "obestavěný prostor", "užitná plocha",
                "spotřeby", "bilance", "náklady", "harmonogram")),

            # ---------------- C. Situační výkresy ----------------
            _R("C", "Situační výkresy", "Celá část C - situační výkresy."),
            _R("C.1", "Situační výkres širších vztahů",
               "Výkres širších vztahů (měřítko min. 1:5000): napojení na "
               "dopravní a technickou infrastrukturu, ochranná a bezpečnostní "
               "pásma.",
               ("situační výkres", "širší vztahy", "1 : 5000", "měřítko")),
            _R("C.2", "Koordinační situační výkres",
               "Koordinační situační výkres (měřítko min. 1:500): polohopis, "
               "hranice pozemků, odstupy, požárně nebezpečné prostory, "
               "technická infrastruktura.",
               ("koordinační situační", "měřítko", "hranice pozemků",
                "odstupové vzdálenosti")),

            # ---------------- D. Dokumentace objektů ----------------
            _R("D", "Dokumentace objektů a technických a technologických "
               "zařízení", "Celá část D."),
            _R("D.1", "Dokumentace stavebního nebo inženýrského objektu",
               "Dokumentace objektu: architektonicko-stavební řešení, "
               "konstrukční řešení, požárně bezpečnostní řešení, technika "
               "prostředí.",),
            _R("D.1.1", "Architektonicko-stavební řešení",
               "Technická zpráva: účel objektu, funkční náplň, kapacitní "
               "údaje; architektonické/výtvarné/materiálové/dispoziční "
               "řešení, bezbariérovost; výkresová část: situační, půdorysy, "
               "pohledy, řezy, detaily.",
               ("technická zpráva", "architektonické řešení", "půdorys",
                "fasáda", "pohledy")),
            _R("D.1.2", "Stavebně konstrukční řešení",
               "Popis nosného systému, základy, konstrukcí, střešního pláště, "
               "přesnější popis uzlů; podrobný statický výpočet.",
               ("nosný systém", "statický výpočet", "konstrukční řešení",
                "základy")),
            _R("D.1.3", "Požárně bezpečnostní řešení",
               "Revize/doplnění požárně bezpečnostního řešení z dokumentace "
               "pro stavební povolení, včetně vyznačení změn.",
               ("požárně bezpečnostní", "PBŘ", "požární")),
            _R("D.1.4", "Technika prostředí staveb",
               "Dokumentace jednotlivých profesí: zdravotně technické "
               "instalace, plyn, vzduchotechnika, vytápění, chlazení, "
               "měření a regulace, silnoproudá elektrotechnika, "
               "sdělovací technika, vnitřní doprava a dopravní zařízení.",
               ("zdravotně technické", "plynová", "vzduchotechnika",
                "vytápění", "elektrotechnika", "měření a regulace")),
            _R("D.2", "Dokumentace technických a technologických zařízení",
               "Technická zpráva zařízení: popis účelu, technologického "
               "procesu, potřeby energií/paliv/vody, bezpečnost a ochrana "
               "životního prostředí.",
               ("technologická zařízení", "trafostanice", "technologický "
                "proces")),

            # ---------------- Dokladová část ----------------
            _R("DOKLADY", "Dokladová část",
               "Vyjmenování přiložené dokladové části: vytyčovací výkresy, "
               "projekt báňského projektanta, atesty, prohlášení o vlastnostech "
               "stavebních výrobků, příp. další doklady dle zvláštních "
               "předpisů.",
               ("dokladová část", "vytyčovací výkres", "atesty", "prohlášení"),
               not_applicable_allowed=True),
        ])
