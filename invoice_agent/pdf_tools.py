"""Document loading + text utilities for the Annex 13 checker agent.

Supports PDF (pypdf) and DOCX (python-docx). DOCX is chunked into
~2 500-char synthetic "pages" (headings start new chunks) so the agent
uses the same read_page/search_pdf tools for both formats.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from pypdf import PdfReader

# Precompiled regexes
_WS = re.compile(r"[ \t]+")
_NL = re.compile(r"\n{3,}")
# TOC detection: dotted leaders ("B.2 Celkový popis ..... 13"), trailing page
# numbers, or an explicit "OBSAH" heading
_TOC_HINT = re.compile(r"^\s*(obsah|obsah:\s*$|table of contents|inhaltsverzeichnis)",
                       re.IGNORECASE | re.MULTILINE)
_TOC_LEADER = re.compile(r"\.{4,}\s*\d+\s*$")
_TOC_PAGE_NUM = re.compile(r"\s\d{1,4}\s*$")


class OCR:
    """Lazy tesseract OCR for scanned pages. Degrades loudly, never silently:

    if unavailable, _from_pdf warns and affected pages stay empty (verdicts
    touching them must be uncertain, which skip-fill guarantees)."""

    reason: str | None = None
    used: bool = False          # set True when any page actually got OCR'd
    pages: set[int] = set()     # page numbers OCR'd in the last load

    @classmethod
    def available(cls) -> bool:
        try:
            import pytesseract  # noqa: F401
            from pdf2image import convert_from_path  # noqa: F401
        except Exception as exc:  # ImportError or pdf2image without poppler
            OCR.reason = f"python deps missing: {exc}"
            return False
        import shutil
        if not shutil.which("tesseract"):
            OCR.reason = "tesseract binary not found (brew install tesseract tesseract-lang)"
            return False
        return True

    @staticmethod
    def page_text(path: str, page_no: int) -> str:
        from pdf2image import convert_from_path
        import pytesseract

        images = convert_from_path(path, dpi=200,
                                   first_page=page_no, last_page=page_no)
        if not images:
            return ""
        out = []
        for img in images:
            text = pytesseract.image_to_string(img, lang="ces+eng")
            text = _WS.sub(" ", text.replace(" ", " "))
            out.append(_NL.sub("\n\n", text).strip())
        return "\n\n".join(out)

_DOCX_CHUNK_SIZE = 2500


class PdfDocument:
    """Text of a document split into pages (PDF) or chunks (DOCX)."""

    def __init__(self, path: str):
        suffix = Path(path).suffix.lower()
        if suffix == ".pdf":
            self.pages = self._from_pdf(path)
        elif suffix == ".docx":
            self.pages = self._from_docx(path)
        else:
            raise ValueError(f"Unsupported file type '{suffix}': {path}")
        self.toc_pages = self._detect_toc()

    def _detect_toc(self) -> set[int]:
        """Pages that look like a table of contents (TOC) — evidence found
        only there is weak (headline, not content)."""
        toc = set()
        for i, text in enumerate(self.pages, start=1):
            if not text:
                continue
            if _TOC_HINT.search(text):
                # density of dotted leaders / page numbers at line ends
                lines = [l for l in text.splitlines() if l.strip()]
                if not lines:
                    continue
                leader_lines = sum(
                    1 for l in lines
                    if _TOC_LEADER.search(l) or _TOC_PAGE_NUM.search(l)
                )
                if len(lines) >= 5 and leader_lines / len(lines) >= 0.6:
                    toc.add(i)
        return toc

    @staticmethod
    def _from_pdf(path: str) -> list[str]:
        reader = PdfReader(path)
        pages = []
        for page in reader.pages:
            raw = page.extract_text() or ""
            raw = raw.replace(" ", " ")
            raw = _WS.sub(" ", raw)
            raw = _NL.sub("\n\n", raw).strip()
            pages.append(raw)
        # scanned/image-only pages -> OCR fallback (Czech + English)
        empty = [i for i, t in enumerate(pages) if not t]
        OCR.pages = set()
        if empty:
            if OCR.available():
                for i in empty:
                    pages[i] = OCR.page_text(path, i + 1)
                    OCR.pages.add(i + 1)
                    OCR.used = True
            else:
                import sys
                print(f"[pdf_tools] WARNING: {len(empty)} page(s) have no text "
                      f"and OCR is unavailable ({OCR.reason}). They will read "
                      f"as empty; verdicts for their content are uncertain.",
                      file=sys.stderr)
        return pages

    @staticmethod
    def _from_docx(path: str) -> list[str]:
        """Docx -> chunks. Headings start a new chunk (keeps structure
        searchable); tables chunked by rows; ~2.5k chars per chunk."""
        from docx import Document
        from docx.table import Table
        from docx.text.paragraph import Paragraph

        doc = Document(path)
        chunks: list[str] = []
        buf: list[str] = []
        size = 0

        def flush():
            nonlocal buf, size
            if buf:
                text = _NL.sub("\n\n", "\n".join(buf)).strip()
                if text:
                    chunks.append(text)
            buf, size = [], 0

        for child in doc.element.body.iterchildren():
            tag = child.tag.rsplit("}", 1)[-1]
            if tag == "p":
                p = Paragraph(child, doc)
                text = p.text.strip()
                if not text:
                    continue
                style = p.style.name or ""
                if style.startswith("Heading"):
                    flush()
                    chunks.append(f"[{p.style.name}] {text}")
                    continue
                buf.append(text)
                size += len(text) + 1
                if size >= _DOCX_CHUNK_SIZE:
                    flush()
            elif tag == "tbl":
                flush()
                t = Table(child, doc)
                lines = [" | ".join(c.text.strip().replace("\n", " ")
                                    for c in row.cells) for row in t.rows]
                group: list[str] = []
                n = 0
                for line in lines:
                    buf.append(line)
                    n += len(line)
                    if n >= _DOCX_CHUNK_SIZE:
                        chunks.append("\n".join(buf))
                        buf, n = [], 0
                if buf:
                    chunks.append("\n".join(buf))

        flush()
        return chunks

    @property
    def full_text(self) -> str:
        return "\n\n".join(self.pages)

    def page_count(self) -> int:
        return len(self.pages)


@lru_cache(maxsize=8)
def load_pdf(path: str) -> PdfDocument:
    return PdfDocument(path)


def search_pages(pdf: PdfDocument, query: str, max_hits: int = 10) -> list[dict]:
    """Case/diacritics-insensitive substring search across pages.

    Returns list of {page, excerpt} dicts. Hits on TOC pages carry a
    "toc": True marker — they prove a headline, not real content.
    """
    norm = _normalize(query)
    if not norm:
        return []
    hits: list[dict] = []
    for i, page in enumerate(pdf.pages, start=1):
        npage = _normalize(page)
        start = 0
        while True:
            pos = npage.find(norm, start)
            if pos == -1:
                break
            # map back to roughly the same char span in the raw page
            excerpt = page[max(0, int(pos * 0.95)): int(pos * 0.95) + len(query) + 160]
            hits.append({"page": i, "excerpt": excerpt.strip(),
                         "toc": i in pdf.toc_pages})
            start = pos + len(norm)
            if len(hits) >= max_hits:
                return hits
    return hits


def _normalize(text: str) -> str:
    """Lowercase and strip Czech diacritics so 'půdorys' matches 'pudorys' etc."""
    return _normalize_text(text)


def _normalize_text(text: str) -> str:
    """Lowercase and strip Czech diacritics so 'půdorys' matches 'pudorys' etc."""
    text = text.lower()
    table = str.maketrans(
        "áčďéěíľĺňóôőŕřšťúůűýž",
        "acdeeillnooorrstuuuyz",
    )
    return text.translate(table)
