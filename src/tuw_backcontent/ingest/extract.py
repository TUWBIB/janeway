"""
Low-level PDF layer extraction.

A PDF carries several independent views of the same document:

* the text/layout view (spans with position and font),
* the document outline (bookmarks, with target pages),
* the annotations (link URIs such as ORCID icons or DOI links),
* the XMP / document info metadata.

This module exposes each layer separately, with geometry in PDF points
(origin top-left), so that higher-level code can join layers spatially
(e.g. a link-annotation rect to the author span it decorates).
"""

import re
from dataclasses import dataclass

import pymupdf

# XMP namespaces we care about
_XMP_DC_RE = re.compile(
    r'<dc:(creator|title|description|subject|identifier|date)>(?P<val>.*?)(?:</dc:\1>|/>)',
    re.S,
)
_XMP_PRISM_RE = re.compile(
    r'<prism:(?P<name>[a-zA-Z]+)>(?P<val>.*?)(?:</prism:\1>|/>)',
    re.S,
)


@dataclass
class Span:
    """One run of text with identical font/size, with its bounding box."""

    text: str
    bbox: tuple  # (x0, y0, x1, y1)
    size: float
    font: str
    flags: int  # bit 4 (16) bold, bit 1 (2) italic in pymupdf span flags
    page: int  # 0-based

    @property
    def is_bold(self):
        return bool(self.flags & 2 ** 4)

    @property
    def is_italic(self):
        return bool(self.flags & 2 ** 1)

    @property
    def baseline(self):
        """Vertical position used for grouping spans into lines."""
        return self.bbox[1]


@dataclass
class Link:
    """A link annotation with a URI, including its on-page source rect."""

    uri: str
    rect: tuple  # (x0, y0, x1, y1)
    page: int  # 0-based


@dataclass
class OutlineItem:
    """One bookmark entry: candidate section/chapter title + target page."""

    title: str
    level: int
    page: int  # 0-based


def spans_all(doc):
    """L1: every text span on every page, with font/size/geometry."""
    out = []
    for pno, page in enumerate(doc):
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line["spans"]:
                    out.append(
                        Span(
                            text=span["text"],
                            bbox=tuple(span["bbox"]),
                            size=span["size"],
                            font=span["font"],
                            flags=span["flags"],
                            page=pno,
                        )
                    )
    return out


def links_all(doc):
    """L3: all link annotations carrying a URI (ORCID icons, DOI, mailto)."""
    out = []
    for pno, page in enumerate(doc):
        for link in page.get_links():
            uri = link.get("uri") or ""
            if link.get("kind") == pymupdf.LINK_URI and uri:
                out.append(
                    Link(uri=uri, rect=tuple(link["from"]), page=pno)
                )
    return out


def outline(doc):
    """L2: document outline / bookmarks -> candidate section titles.

    Returns entries sorted by target page. Pages are 1-based in the
    PDF outline and converted to 0-based here.
    """
    items = []
    for level, title, page_number in doc.get_toc(simple=True):
        items.append(OutlineItem(title=title, level=level, page=page_number - 1))
    items.sort(key=lambda i: i.page)
    return items


def xmp(doc):
    """L4: document-level info dict plus any raw XMP metadata stream.

    Returns ``{"meta": {...}, "xmp": {...}}`` where ``xmp`` holds the
    parsed Dublin Core and PRISM fields (empty dicts when absent).
    """
    meta = {k: v for k, v in (doc.metadata or {}).items() if v}
    xmp_fields = {}
    try:
        _, value = doc.xref_get_key(doc.pdf_catalog(), "Metadata")
        if value and value[0] == "xref":
            raw = doc.xref_stream(int(value[1])).decode("utf-8", "replace")
            for m in _XMP_DC_RE.finditer(raw):
                xmp_fields.setdefault("dc", {})[m.group(1)] = m.group("val").strip()
            for m in _XMP_PRISM_RE.finditer(raw):
                xmp_fields.setdefault("prism", {})[m.group("name")] = m.group("val").strip()
    except Exception:
        pass  # no XMP stream, or unreadable: not fatal
    return {"meta": meta, "xmp": xmp_fields}


def profile(doc, spans, links, toc, xmp_data):
    """S0: routing information for the whole document.

    Flags scanned documents (no text layer at all -> both the textual and
    the structural paths are dead; OCR upstream is required) and reports
    which layers are present. Built from the already-extracted layers so
    nothing is parsed twice.
    """
    return {
        "producer": (doc.metadata or {}).get("producer", ""),
        "pages": doc.page_count,
        "has_text": bool(spans),
        "has_outline": bool(toc),
        "n_spans": len(spans),
        "n_links": len(links),
        "has_xmp": bool(xmp_data.get("xmp")),
    }


class IngestError(Exception):
    """Raised when the document cannot be ingested at all."""
