"""Document loading + text utilities.

`Document` holds the text of one file split into pages (PDF) or chunks
(DOCX), with TOC detection and OCR fallback for scanned pages. New formats
extend the loader dispatch in `Document._load_pages`.
"""

from __future__ import annotations

import re
import shutil
import sys
from functools import lru_cache
from pathlib import Path

from pypdf import PdfReader

_WS = re.compile(r"[ \t]+")
_NL = re.compile(r"\n{3,}")
_TOC_HINT = re.compile(r"^\s*(obsah|table of contents|inhaltsverzeichnis)",
                       re.IGNORECASE | re.MULTILINE)
_TOC_LEADER = re.compile(r"\.{4,}\s*\d+\s*$")
_TOC_PAGE_NUM = re.compile(r"\s\d{1,4}\s*$")
_DOCX_CHUNK_SIZE = 2500


class OcrEngine:
    """Tesseract OCR for scanned pages. Degrades loudly, never silently:
    when unavailable, affected pages stay empty and the verifier keeps
    their verdicts uncertain."""

    def __init__(self):
        self.reason: str | None = None
        self._checked = False
        self._ok = False

    def available(self) -> bool:
        if not self._checked:
            self._checked = True
            try:
                import pytesseract  # noqa: F401
                from pdf2image import convert_from_path  # noqa: F401
                self._ok = bool(shutil.which("tesseract"))
                if not self._ok:
                    self.reason = ("tesseract binary not found "
                                   "(brew install tesseract tesseract-lang)")
            except Exception as exc:
                self.reason = f"OCR deps missing: {exc}"
        return self._ok

    def page_text(self, path: Path, page_no: int) -> str:
        from pdf2image import convert_from_path
        import pytesseract

        images = convert_from_path(path, dpi=200,
                                   first_page=page_no, last_page=page_no)
        out = []
        for img in images:
            text = pytesseract.image_to_string(img, lang="ces+eng")
            text = _WS.sub(" ", text.replace(" ", " "))
            out.append(_NL.sub("\n\n", text).strip())
        return "\n\n".join(out)


class Document:
    """One loaded document: text pages/chunks + TOC detection."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        suffix = self.path.suffix.lower()
        if suffix not in (".pdf", ".docx"):
            raise ValueError(f"Unsupported file type '{suffix}': {self.path}")
        self.pages: list[str] = self._load()
        self.toc_pages = self._detect_toc()
        self.ocr_pages: set[int] = set()

    def page_count(self) -> int:
        return len(self.pages)

    @property
    def unit(self) -> str:
        """Name of the positional unit ('stran' vs 'chunk') for messages."""
        return "chunků" if self.path.suffix.lower() == ".docx" else "stran"

    # ---- PDF -----------------------------------------------------------

    def _load(self) -> list[str]:
        return self._from_pdf(self.path) if self.path.suffix.lower() == ".pdf" \
            else self._from_docx(self.path)

    def _from_pdf(self, path: Path) -> list[str]:
        from pypdf import PdfReader

        pages = []
        for page in PdfReader(str(path)).pages:
            raw = (page.extract_text() or "").replace(" ", " ")
            pages.append(_NL.sub("\n\n", _WS.sub(" ", raw)).strip())

        empty = [i for i, t in enumerate(pages) if not t]
        if not empty:
            return pages

        ocr = OcrEngine()
        if ocr.available():
            self.ocr_pages = set()
            for i in empty:
                pages[i] = ocr.page_text(str(path), i + 1)
                self.ocr_pages.add(i + 1)
        else:
            print(f"[dovera] WARNING: {len(empty)} page(s) have no text and OCR "
                  f"is unavailable ({ocr.reason}). Verdicts for their content "
                  "are uncertain.", file=sys.stderr)
        return pages

    def _from_docx(self, path: Path) -> list[str]:
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
                para = Paragraph(child, doc)
                text = para.text.strip()
                if not text:
                    continue
                if (para.style.name or "").startswith("Heading"):
                    flush()
                    chunks.append(f"[{para.style.name}] {text}")
                    continue
                buf.append(text)
                size += len(text) + 1
                if size >= _DOCX_CHUNK_SIZE:
                    flush()
            elif tag == "tbl":
                flush()
                table = Table(child, doc)
                for row in table.rows:
                    line = " | ".join(c.text.strip().replace("\n", " ")
                                      for c in row.cells)
                    buf.append(line)
                    size += len(line) + 1
                    if size >= _DOCX_CHUNK_SIZE:
                        flush()
        flush()
        return chunks

    def _detect_toc(self) -> set[int]:
        toc = set()
        for i, text in enumerate(self.pages, start=1):
            if not text or not _TOC_HINT.search(text):
                continue
            lines = [l for l in text.splitlines() if l.strip()]
            leaders = sum(1 for l in lines
                          if _TOC_LEADER.search(l) or _TOC_PAGE_NUM.search(l))
            if len(lines) >= 5 and leaders / len(lines) >= 0.6:
                toc.add(i)
        return toc


@lru_cache(maxsize=8)
def load_document(path: str) -> Document:
    return Document(path)


def normalize_text(text: str) -> str:
    """Lowercase and strip Czech diacritics so 'půdorys' matches 'pudorys'."""
    return text.lower().translate(str.maketrans(
        "áčďéěíľĺňóôőŕřšťúůűýž", "acdeeillnooorrstuuuyz"))


def squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def search_pages(doc: Document, query: str, max_hits: int = 10) -> list[dict]:
    """Case/diacritics-insensitive search. TOC-page hits carry "toc": True —
    they prove a headline, not content."""
    needle = normalize_text(query)
    if not needle:
        return []
    hits = []
    for i, page in enumerate(doc.pages, start=1):
        haystack = normalize_text(page)
        start = 0
        while (pos := haystack.find(needle, start)) != -1:
            excerpt = page[max(0, int(pos * 0.95)): int(pos * 0.95) + len(query) + 160]
            hits.append({"page": i, "excerpt": excerpt.strip(),
                         "toc": i in doc.toc_pages})
            start = pos + len(needle)
            if len(hits) >= max_hits:
                return hits
    return hits
