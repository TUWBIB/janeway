"""
Pipeline orchestration: open the PDF, extract all layers, segment,
extract fields, optionally enrich, and return a provenance-tagged
artifact.
"""

import pymupdf

from . import enrich, extract, fields, segments
from .extract import IngestError


def run(path, enrich_=False):
    """Extract all metadata from the PDF at ``path``.

    :param path: filesystem path of the PDF.
    :param enrich_: when True, run the optional network enrichment pass
        (ORCID verification, Crossref DOI resolution).
    :return: ``{"profile": {...}, "articles": [ {...}, ... ]}``
    :raises IngestError: when the document is empty or has no text layer
        (scanned document -> OCR upstream first).
    """
    doc = pymupdf.open(path)
    try:
        spans = extract.spans_all(doc)
        links = extract.links_all(doc)
        toc = extract.outline(doc)
        xmp_data = extract.xmp(doc)
        profile = extract.profile(doc, spans, links, toc, xmp_data)

        if not profile["has_text"]:
            raise IngestError(
                "PDF has no text layer (scanned document); run an OCR step "
                "(e.g. ocrmypdf) before ingesting."
            )

        segs = segments.segment(doc, spans, toc)
        articles = []
        for seg in segs:
            article = fields.extract_all(seg, spans, links, xmp_data)
            if enrich_:
                article = enrich.enrich(article)
            articles.append(article)

        return {"profile": profile, "articles": articles}
    finally:
        doc.close()
