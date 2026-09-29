"""Generate synthetic Czech construction-documentation PDFs for testing.

complete_project.pdf  — contains all Annex 13 sections (agent should pass)
incomplete_project.pdf — missing several required items (agent should flag)
"""

from __future__ import annotations

import os

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

# Arial Unicode covers Czech diacritics (p, ř, ě, š ...)
_ARIAL = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
pdfmetrics.registerFont(TTFont("ArialUni", _ARIAL))
_BASE = dict(fontName="ArialUni", fontSize=10, leading=14)


def _style(name: str, size: int, extra: dict | None = None) -> ParagraphStyle:
    kw = dict(_BASE)
    kw["fontName"] = "ArialUni"
    kw["fontSize"] = size
    kw["leading"] = size + 4
    if extra:
        kw.update(extra)
    return ParagraphStyle(name, **kw)


NORMAL = _style("Normal", 10)
H1 = _style("H1", 16, extra={"spaceAfter": 6})
H2 = _style("H2", 13)
H3 = _style("H3", 11)

OUT_DIR = os.path.join(os.path.dirname(__file__), "data")


def build_pdf(path: str, blocks: list[tuple[str, str]]):
    doc = SimpleDocTemplate(path, pagesize=A4,
                            leftMargin=25 * mm, rightMargin=25 * mm,
                            topMargin=20 * mm, bottomMargin=20 * mm)
    story = []
    for kind, text in blocks:
        if kind == "h1":
            story.append(Paragraph(text, H1))
        elif kind == "h2":
            story.append(Paragraph(text, H2))
        elif kind == "h3":
            story.append(Paragraph(text, H3))
        else:
            story.append(Paragraph(text, NORMAL))
        story.append(Spacer(1, 4 * mm))
    doc.build(story)


COMPLETE = [
    ("h1", "PROJEKTOVÁ DOKUMENTACE PRO PROVÁDĚNÍ STAVBY"),
    ("h2", "A. Průvodní zpráva"),
    ("h3", "A.1 Identifikační údaje"),
    ("h3", "A.1.1 Údaje o stavby"),
    ("p", "Název stavby: Bytový dům Zelená 12, Brno. "
          "Místo stavby: Brno-Jundrov, katastrální území Brno-Jundrov, "
          "parcelní čísla pozemků 1234/5, 1235, čísla popisná 456."),
    ("h3", "A.1.2 Údaje o stavebníkovi"),
    ("p", "Stavebník: Stavební spol. s r.o., IČO 12345678, adresa sídla "
          "Zelená 12, 602 00 Brno."),
    ("h3", "A.1.3 Údaje o zpracovateli projektové dokumentace"),
    ("p", "Zpracovatel: Projekce a.s., IČO 87654321, sídlo Kounicova 5, Brno. "
          "Hlavní projektant: Ing. Jan Novák, autorizační číslo ČKAIT 0123456-AAPC, "
          "obor pozemní stavby. Projektanti jednotlivých částí: Ing. Marie Svobodová, "
          "autorizace ČKAIT 0234567-AAPS, obor statika."),
    ("h3", "A.2 Členění stavby na objekty a technická a technologická zařízení"),
    ("p", "Stavba se člení na objekty: objekt A (bytový dům), objekt B (garáže) "
          "a technická a technologická zařízení - trafostanice, měníčka."),
    ("h3", "A.3 Seznam vstupních podkladů"),
    ("p", "Rozhodnutí: stavební povolení Stavebního úřadu Brno-město, "
          "číslo jednací SPP/12345/2024, datum vyhotovení 15. 3. 2024. "
          "Předchozí dokumentace: projektová dokumentace pro vydání stavebního povolení, "
          "zpracoval Projekce a.s., 2023. Další podklady: geologický průzkum, "
          "vyjádření dotčených orgánů."),
    ("h2", "B. Souhrnná technická zpráva"),
    ("p", "Požadavky na zpracování dodavatelské dokumentace stavby: vypracuje zhotovitel "
          "dle výkazů výměr. Požadavky na zpracování plánu bezpečnosti a ochrany zdraví "
          "při práci na staveništi: plán BOZP zpracuje dodavatel. Podmínky realizace prací "
          "v ochranných pásmech: dodržet pásmo vodovodu. Zvláštní podmínky a požadavky "
          "na organizaci staveniště: přístup z ulice Zelené. Ochrana životního prostředí "
          "při výstavbě: odklízení sněhu, hlukové limity."),
    ("h3", "B.1 Popis území stavby"),
    ("p", "Charakteristika území a stavebního pozemku: území zastavěné, souhlas "
          "s charakterem území. Soulad s územním rozhodnutím čj. ÚR/2233/2022. "
          "Soulad s územně plánovací dokumentací: záměrný plán Brno. "
          "Závazná stanoviska dotčených orgánů: vodoprávní úřad, energetika. "
          "Geologický průzkum proveden, hydrogeologický průzkum proveden. "
          "Ochrana území: záplavové území Q100. Vliv stavby na okolní stavby "
          "a pozemky minimální, ochrana okolí zajištěna. Požadavky na asanace "
          "a demolice: demoloval se objekt C. Zábory zemědělského půdního fondu: "
          "žádné. Územně technické podmínky: napojení na dopravní a technickou "
          "infrastrukturu možné, bezbariérový přístup zajištěn. Věcné a časové vazby: "
          "navazuje na rekonstrukci sítě. Seznam pozemků podle katastru nemovitostí: "
          "parcela 1234/5, 1235 (k. ú. Brno-Jundrov)."),
    ("h3", "B.2 Celkový popis stavby"),
    ("p", "Nová stavba. Účel užívání stavby: bydlení. Trvalá stavba. "
          "Parametry stavby: zastavěná plocha 850 m2, obestavěný prostor 12 300 m3, "
          "užitná plocha 3 200 m2, 45 funkčních jednotek. Základní bilance stavby: "
          "potřeby a spotřeby médií - voda 12 m3/den, elektřina 350 kW, "
          "hospodaření s dešťovou vodou - zadržovací nádrž, produkované odpady "
          "a emise dle vyjádření, třída energetické náročnosti B. "
          "Základní předpoklady výstavby: realizace v jedné etapě, časový plán 14 měsíců. "
          "Orientační náklady stavby: 165 mil. Kč."),
    ("h2", "C. Situační výkresy"),
    ("h3", "C.1 Situační výkres širších vztahů"),
    ("p", "Měřítko 1 : 5000. Napojení stavby na dopravní a technickou infrastrukturu "
          "zobrazeno. Stávající a navrhovaná ochranná a bezpečnostní pásma vyznačena. "
          "Hranice dotčeného území vyznačeny."),
    ("h3", "C.2 Koordinační situační výkres"),
    ("p", "Měřítko 1 : 500. Stávající stavby, dopravní a technická infrastruktura. "
          "Hranice pozemků, parcelní čísla. Hranice řešeného území. "
          "Stávající výškopis a polohopis. Vyznačení jednotlivých navržených "
          "a odstraňovaných staveb. Stanovení nadmořské výšky 1. nadzemního podlaží "
          "(± 0,00 = 214,50 m n. m.), maximální výška staveb 18,5 m. "
          "Navrhované komunikace a zpevněné plochy. Řešení vegetace. "
          "Okótované odstupy staveb. Zákres nové technické infrastruktury. "
          "Stávající a navrhovaná ochranná a bezpečnostní pásma. "
          "Maximální dočasné a trvalé zábory. Vyznačení geotechnických sond S1-S8. "
          "Geodetické údaje, určení souřadnic vytyčovací sítě. "
          "Zařízení staveniště s vyznačením vjezdu. Odstupové vzdálenosti včetně "
          "vymezení požárně nebezpečných prostorů, přístupové komunikace a nástupní "
          "plochy pro požární techniku a zdroje požární vody."),
    ("h2", "D. Dokumentace objektů a technických a technologických zařízení"),
    ("h3", "D.1 Dokumentace stavebního nebo inženýrského objektu"),
    ("h2", "D.1.1 Architektonicko-stavební řešení"),
    ("p", "Technická zpráva: účel objektu - bydlení, funkční náplň, kapacitní údaje "
          "(45 bytů). Architektonické, výtvarné, materiálové a dispoziční řešení, "
          "bezbariérové užívání stavby. Celkové provozní řešení. Konstrukční "
          "a stavebně technické řešení. Stavební fyzika - tepelná technika, "
          "osvětlení, oslunění, akustika - hluk, vibrace. Zásady hospodaření energiemi. "
          "Bezpečnost při užívání stavby, ochrana zdraví a pracovní prostředí. "
          "Požadavky na požární ochranu konstrukcí. Údaje o požadované jakosti "
          "navržených materiálů. Kontroly zakrývaných konstrukcí. Výpis použitých norem."),
    ("p", "Výkresová část: výkresy stavební jámy, půdorysy jednotlivých podlaží "
          "s rozměrovými kótami, popisem účelu využití místností s plošnou výměrou. "
          "Charakteristické řezy s výškovými kótami. Výkresy střechy a krovu. "
          "Pohledy na všechny plochy fasády s výškovými kótami, barevností "
          "a charakteristikou materiálů povrchů."),
    ("p", "Dokumenty podrobností: skladby konstrukcí, seznamy částí, výrobků a prací, "
          "rozhodující detaily konstrukcí, detaily bezbariérových opatření."),
    ("h2", "D.1.2 Stavebně konstrukční řešení"),
    ("p", "Technická zpráva: podrobný popis navrženého nosného systému stavby "
          "(železobetonový skelet), definitivní průřezové rozměry konstrukčních prvků, "
          "údaje o uvažovaných zatíženích ve statickém výpočtu (stálá, užitná, "
          "klimatická), údaje o požadované jakosti materiálů, zajištění stavební jámy "
          "sheet pilotami, kontroly zakrývaných konstrukcí, výpis použitých podkladů."),
    ("p", "Podrobný statický výpočet: průvodní zpráva ke statickému výpočtu, "
          "použité podklady - normy, výpočetní programy, statické schéma konstrukce, "
          "údaje o materiálech, rekapitulace zatížení a zatěžovacích stavů, "
          "výpočetní modely, návrh a posouzení všech nosných prvků, výpočet účinků "
          "na základy, dimenzování základových konstrukcí, návrh detailů a montážních "
          "styků, postup výroby - betonáže, odbedňování, montáže."),
    ("p", "Výkresová část: půdorysy nosných konstrukcí v měřítku 1 : 50, řezy "
          "a pohledy, detaily styků v měřítku 1 : 10, výkresy umístění konstrukcí, "
          "výkres uspořádání vyztužení monolitických betonových konstrukcí."),
    ("h2", "D.1.3 Požárně bezpečnostní řešení"),
    ("p", "Revize a doplnění požárně bezpečnostního řešení z dokumentace "
          "pro vydání stavebního povolení, včetně vyznačení změn "
          "v požárně bezpečnostním řešení."),
    ("h2", "D.1.4 Technika prostředí staveb"),
    ("p", "Dokumentace jednotlivých profesí: zdravotně technické instalace, "
          "plynová odběrná zařízení, vzduchotechnika, vytápění, chlazení, "
          "měření a regulace, silnoproudá elektrotechnika včetně ochrany před "
          "bleskem, elektronické komunikace."),
    ("p", "Technická zpráva: bilance potřeby médií a energií, popis technického "
          "řešení a instalace, podmínky připojení na veřejnou technickou "
          "infrastrukturu, zásady bezpečného provozu, požární opatření, ochrana "
          "proti hluku a vibracím, zásady ochrany životního prostředí, technické "
          "výpočty, seznam dokladů nutných pro uvedení stavby do užívání, "
          "výpis použitých norem."),
    ("p", "Výkresová část: situace s přípojkami, rozvinuté řezy přípojek, "
          "umístění strojů a zařízení, výkresy půdorysů potrubních a kabelových tras, "
          "axonometrické zobrazení, instalační výkresy a schémata, přehledové schéma "
          "napájení, schéma uzemňovací a jímací soustavy."),
    ("p", "Seznam strojů a zařízení a technické specifikace: seznam strojů "
          "a zařízení, popis technických a výkonových parametrů, seznamy materiálu "
          "pro konstrukce, rozvody, potrubí, izolace."),
    ("h3", "D.2 Dokumentace technických a technologických zařízení"),
    ("p", "Stavba se člení na provozní celky: trafostanice, sdělovací technika. "
          "Technická zpráva: popis účelu, popis technologického procesu, údaje "
          "o potřebě energií, paliv, vody a jiných médií včetně požadavků "
          "a míst napojení, seznam dokladů nutných pro uvedení stavby do užívání, "
          "výpis použitých norem. Výkresová část: umístění a uspořádání zařízení, "
          "přehledová schémata rozvodů, půdorysy kabelových rozvodů, technologická "
          "schémata. Seznam strojů a zařízení a technické specifikace v příloze."),
    ("h2", "Dokladová část"),
    ("p", "Obsahuje: 1. Vytyčovací výkresy jednotlivých objektů. "
          "2. Projekt zpracovaný báňským projektantem - nevztahuje se, "
          "stavba se nenachází v zájmovém území báňské činnosti."),
]

INCOMPLETE = [
    ("h1", "PROJEKTOVÁ DOKUMENTACE PRO PROVÁDĚNÍ STAVBY"),
    ("h2", "A. Průvodní zpráva"),
    ("h3", "A.1 Identifikační údaje"),
    ("p", "Název stavby: Rodinný dům Lískovec. Místo stavby: Brno-Lískovec, "
          "katastrální území Brno-Lískovec, parcela 5678/12."),
    ("p", "Stavebník: Ing. Petr Dvořák, Brno. "
          "Zpracovatel dokumentace: Inženýrské studio Brno s.r.o."),
    ("p", "Seznam vstupních podkladů: stavební povolení čj. SPP/99887/2024."),
    ("h2", "B. Souhrnná technická zpráva"),
    ("p", "Popis stavby: rodinný dům, účel užívání - bydlení, "
          "zastavěná plocha 120 m2, obestavěný prostor 680 m3."),
    ("h2", "C. Situační výkresy"),
    ("p", "Situační výkres v měřítku 1 : 500."),
    # Chybí: C.1, C.2 detaily, D celé, Dokladová část,
    # A.1.2 (úplné údaje o stavebníkovi), A.1.3 (zpracovatel detaily),
    # A.2, B.1, B.2 bilance, D.1.1 až D.1.4, D.2, Dokladová část
]


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    build_pdf(os.path.join(OUT_DIR, "complete_project.pdf"), COMPLETE)
    build_pdf(os.path.join(OUT_DIR, "incomplete_project.pdf"), INCOMPLETE)
    print(f"Test PDFs written to {OUT_DIR}")


if __name__ == "__main__":
    main()
