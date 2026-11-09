"""
ORCID iD extraction and validation.

An ORCID iD can appear in a PDF in two fundamentally different ways:

* as visible text (printed next to the author's name), and
* only as the URI of a link annotation on an ORCID icon. In that case the
  iD is *not* in the text layer at all; it can only be recovered by
  reading the annotation and then spatially joining it to the author span
  whose line the icon decorates.

Both sources are fused here, with the annotation taking precedence and
the canonical ISO/IEC 7064 mod 11-2 checksum guarding against typos and
OCR damage.
"""

import re

# Full ORCID iD, e.g. 0000-0002-1825-0097 (16 chars incl. dashes; last is a digit or X).
ORCID_ID_RE = re.compile(r"\d{4}-\d{4}-\d{4}-\d{3}[\dX]")

# ORCID iD hidden in a link-annotation URI.
ORCID_URI_RE = re.compile(r"orcid\.org/(\d{4}-\d{4}-\d{4}-\d{3}[\dX])", re.I)


def checksum_valid(orcid_id):
    """Validate the ISO/IEC 7064 mod 11-2 check digit of an ORCID iD.

    Returns True only for well-formed iDs (16 body chars) with a correct
    final check character.
    """
    if not orcid_id:
        return False
    body = orcid_id.replace("-", "")
    if len(body) != 16:
        return False
    total = 0
    for ch in body[:15]:
        total = (total + (10 if ch.upper() == "X" else int(ch))) * 2
    check = (12 - (total % 11)) % 11
    expected = "X" if check == 10 else str(check)
    return body[15].upper() == expected


def normalize(orcid_id):
    """Uppercase and strip whitespace; returns '' when empty."""
    return (orcid_id or "").strip().upper()


def from_text(text):
    """First checksum-valid ORCID iD printed in ``text``, else None."""
    for m in ORCID_ID_RE.finditer(text or ""):
        candidate = m.group(0)
        if checksum_valid(candidate):
            return candidate
    return None


def from_link(link):
    """ORCID iD carried by a link-annotation URI (the icon case), else None."""
    m = ORCID_URI_RE.search(link.uri or "")
    if not m:
        return None
    candidate = m.group(1).upper()
    return candidate if checksum_valid(candidate) else None


def resolve(author_span, links, line_text=None):
    """Fuse ORCID sources for a single author.

    :param author_span: the :class:`Span` holding the author's name.
    :param links: all :class:`~tuw_backcontent.ingest.extract.Link` objects
        on that author's page.
    :param line_text: optional pre-joined text of the author's line(s).
    :return: ``(orcid, source)`` where ``source`` is one of
        ``'annotation'``, ``'text'``, or ``None``.
    """
    # 1. Annotation: a link whose icon rect sits on the same line, at or to
    #    the right of the author span. This is the case invisible to a
    #    pure text read.
    for link in links:
        if link.page != author_span.page:
            continue
        same_line = abs(link.rect[1] - author_span.bbox[1]) < 10
        right_of = link.rect[0] >= author_span.bbox[0]
        if same_line and right_of:
            orcid = from_link(link)
            if orcid:
                return orcid, "annotation"

    # 2. Visible text on the author's line (and, if the iD wraps, the
    #    following line).
    if line_text is None:
        line_text = ""
    orcid = from_text(line_text)
    if orcid:
        return orcid, "text"

    return None, None
