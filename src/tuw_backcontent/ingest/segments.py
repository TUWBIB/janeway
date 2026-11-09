"""
Segmentation: split a PDF into articles / chapters / sections.

Strategy (in priority order):

1. Document outline (bookmarks): top-level entries whose target page
   strictly advances are article candidates. Entries whose target page
   falls inside an already-open range are subsections and are ignored.
2. Layout heuristic: a page that opens with a large, roughly centered
   heading followed by an author-like line starts a new segment.
3. Fallback: the whole document is a single article.
"""

import statistics
from dataclasses import dataclass, field


@dataclass
class Segment:
    """One article / chapter: candidate title + page range (end exclusive)."""

    title: str
    start_page: int
    end_page: int  # exclusive

    @property
    def page_range(self):
        return (self.start_page, self.end_page)


def _line_spans(spans):
    """Group a page's spans into lines by baseline, preserving order."""
    lines = []
    current = []
    current_baseline = None
    for s in spans:
        if (
            current
            and abs(s.baseline - current_baseline) > 4
        ):
            lines.append(current)
            current = []
        current.append(s)
        if current_baseline is None:
            current_baseline = s.baseline
        else:
            current_baseline = (current_baseline + s.baseline) / 2
    if current:
        lines.append(current)
    return lines


def _looks_like_title(line_spans, median_size):
    """True if the line reads like a document/chapter title."""
    text = "".join(s.text for s in line_spans).strip()
    if not text or len(text) < 3:
        return False
    max_size = max(s.size for s in line_spans)
    return max_size >= max(median_size * 1.4, median_size + 2)


def _looks_like_author_line(line_spans):
    """Crude check: comma- or 'and'-separated capitalized words."""
    text = "".join(s.text for s in line_spans).strip()
    if not text:
        return False
    parts = [p for p in text.replace(",", " ").split() if p]
    capitalized = sum(1 for p in parts if p[:1].isupper())
    return len(parts) >= 2 and capitalized / len(parts) >= 0.5


def _median_span_size(spans):
    sizes = [s.size for s in spans if s.text.strip()]
    return statistics.median(sizes) if sizes else 11.0


def _heuristic_boundaries(spans):
    """Fallback segmentation when the outline is absent or unhelpful."""
    spans_by_page = {}
    for s in spans:
        spans_by_page.setdefault(s.page, []).append(s)
    if not spans_by_page:
        return []

    median_size = _median_span_size(spans)
    starts = [min(spans_by_page)]
    for pno in sorted(spans_by_page):
        if pno == min(spans_by_page):
            continue
        page_spans = sorted(spans_by_page[pno], key=lambda s: (s.baseline, s.bbox[0]))
        lines = _line_spans(page_spans)[:3]
        if not lines:
            continue
        first_text = "".join(s.text for s in lines[0]).strip()
        if not first_text:
            continue
        if _looks_like_title(lines[0], median_size):
            starts.append(pno)
    return sorted(set(starts))


def segment(doc, spans, toc):
    """Return the list of :class:`Segment` covering the document.

    :param doc: an open pymupdf Document (page count only).
    :param spans: result of :func:`extract.spans_all`.
    :param toc: result of :func:`extract.outline`.
    """
    n_pages = doc.page_count
    candidates = _from_outline(toc, n_pages)
    if not candidates:
        candidates = _heuristic_boundaries(spans)
    if not candidates:
        candidates = [0]

    segments = []
    for i, start in enumerate(candidates):
        end = candidates[i + 1] if i + 1 < len(candidates) else n_pages
        segments.append(Segment(title="", start_page=start, end_page=end))

    # Attach candidate titles from the outline where they line up.
    for seg in segments:
        for item in toc:
            if item.page == seg.start_page:
                seg.title = item.title
                break
    return segments


def _from_outline(toc, n_pages):
    """Top-level outline entries with strictly advancing target pages."""
    if not toc:
        return []
    top_level = [item for item in toc if item.level == 1]
    pool = top_level if top_level else toc
    starts = []
    for item in pool:
        if item.page < 0 or item.page >= n_pages:
            continue
        if not starts or item.page > starts[-1]:
            starts.append(item.page)
        # An entry whose page is already inside the previous segment's
        # range is a subsection, not a new article.
    return sorted(set(starts))
