"""
Per-segment metadata field extraction.

Every extracted value is a *provenance dict*::

    {"value": ..., "source": "text|outline|link|xmp",
     "page": <0-based page or None>, "confidence": <0.0-1.0>}

so that downstream consumers (review UI, import adapters) can tell where
each value came from and how much to trust it.

The extraction is purely local and spatial: fields are joined to each
other and to link annotations through bbox geometry, never through
assumptions about text order alone.
"""

import re
import unicodedata
from collections import Counter

from . import orcid as orcid_mod


def _normalize_text(text):
    """Compose standalone diacritics into proper umlauts.

    Some PDFs store "ö" as a standalone diaeresis symbol (U+00A8) placed
    *before* the vowel it decorates ("r¨o"), e.g. the name "Grödt" is
    stored as "Gr¨odt". U+00A8 is not composited by NFC, so it is mapped
    to the combining mark U+0308 and, when it sits between a consonant
    and a vowel, moved after the vowel so that NFC composes a proper
    umlaut ("Grödt").
    """
    t = (text or "").replace("\u00a8", "\u0308")
    t = re.sub(
        r"(?P<pre>[^\s\u0300-\u036f])\u0308" r"(?P<v>[a-zA-Z\u00e4\u00f6\u00fc\u00c4\u00d6\u00dc])",
        lambda m: m.group("pre") + m.group("v") + "\u0308",
        t,
    )
    return unicodedata.normalize("NFC", t)

# Known section labels used to bound the abstract / locate the references.
ABSTRACT_LABELS = ("abstract", "res\u00fcm\u00e9", "zusammenfassung")
KEYWORD_LABELS = (
    "keywords",
    "key words",
    "key words and phrases",
    "key words (and phrases)",
    "key words (or phrases)",
    "key words (and/or phrases)",
    "keywords (and/or phrases)",
    "msc",
    "msc 2020",
    "msc 2010",
    "jel",
    "jel codes",
)
REFERENCE_LABELS = ("references", "bibliography", "literatur", "literaturverzeichnis")

DOI_TEXT_RE = re.compile(r"10\.\d{4,9}/[^\s\)\]<]+")
MAILTO_RE = re.compile(r"mailto:([^>\s]+)", re.I)

# Superscript affiliation markers: small raised digits/letters at line end.
SUPERSCRIPT_CHARS = re.compile(r"^[\d\*+a-zA-Z]{1,3}$")


def _value(value, source, page=None, confidence=0.9):
    return {
        "value": value,
        "source": source,
        "page": page,
        "confidence": confidence,
    }


def _segment_spans(seg, spans):
    """Spans belonging to the segment, in reading order."""
    sel = [s for s in spans if seg.start_page <= s.page < seg.end_page]
    return sorted(sel, key=lambda s: (s.page, s.baseline, s.bbox[0]))


def _lines(spans):
    """Group spans into visual lines (baseline tolerance 4pt).

    Spans are sorted by (page, baseline, x) first, then each visual line
    is re-sorted by x: PDF producers do not guarantee that spans appear
    in left-to-right order (they appear in content-stream order), so e.g.
    a superscript marker or the last surname can be emitted before the
    names it belongs to. Baselines of spans on the same visual line can
    differ by fractions of a point, so the within-line order must come
    from x, not from baseline.
    """
    ordered = sorted(spans, key=lambda s: (s.page, s.baseline, s.bbox[0]))
    lines = []
    current = []
    for s in ordered:
        if (
            current
            and (
                s.page != current[0].page
                or abs(s.baseline - current[0].baseline) > 4
            )
        ):
            lines.append(current)
            current = []
        current.append(s)
    if current:
        lines.append(current)
    return [sorted(line, key=lambda s: s.bbox[0]) for line in lines]


def _line_text(line):
    return " ".join(s.text for s in line).strip()


def _body_size(spans):
    """The dominant (most frequent) font size = the body text size.

    Ties (e.g. a 2-span document) resolve to the *smaller* size, because
    the larger one is more likely a heading than the body.
    """
    sizes = [round(s.size, 1) for s in spans if s.text.strip()]
    if not sizes:
        return 11.0
    counts = Counter(sizes)
    max_count = max(counts.values())
    candidates = [sz for sz, c in counts.items() if c == max_count]
    return min(candidates)


def _find_label(lines, labels, start=0):
    """Find the first line starting with a known label.

    Matches both a bare label line ("Abstract") and a label with inline
    content ("Keywords: a, b, c" / "MSC 2020: 68-04"). Returns
    ``(index, label, rest_of_line)`` where ``rest_of_line`` is the text
    following the label (and colon) on the same line, or '' if none.
    """
    for i in range(start, len(lines)):
        raw = _line_text(lines[i]).strip()
        text = raw.lower()
        for label in labels:
            if text == label:
                return i, label, ""
            # Label followed by a separator and inline content:
            # "Keywords: a, b", "Abstract: ...", IEEE-style "Abstract— ..."
            # (colon, em/en dash, or hyphen).
            m = re.match(
                r"^(?P<lab>%s)\s*[:\u2013\u2014-]\s*(?P<rest>.*)$" % re.escape(label),
                text,
                re.I,
            )
            if m:
                return i, label, m.group("rest").strip()
    return None, None, None


# ---------------------------------------------------------------------------
# Title
# ---------------------------------------------------------------------------

def _title_run(lines, seg_spans):
    """Detect the run of heading-sized lines at the top of the segment.

    The title is the first block (within the first few lines of the page)
    whose lines are set in a font clearly larger than the dominant body
    size; the run continues over consecutive lines of that size, which
    covers multi-line titles.

    Returns ``(title_text, end_idx)`` where ``end_idx`` is the line index
    just past the last title line (i.e. the author region starts there),
    or ``("", 0)`` when no heading-sized lines are found (titles set in
    the same size as the body cannot be detected this way).
    """
    body = _body_size(seg_spans)
    threshold = max(body + 1.0, body * 1.1)
    for start in range(min(4, len(lines))):
        if not lines[start]:
            continue
        first_size = max(s.size for s in lines[start])
        if first_size < threshold:
            continue
        # A multi-line title is set in the same size as its first line;
        # the run therefore continues only while the line size matches
        # the first line's size (within 1.5pt). Lines set smaller (e.g.
        # an author line at body size) end the run even though they may
        # still clear the threshold.
        parts, idx = [], start
        while (
            idx < len(lines)
            and lines[idx]
            and abs(max(s.size for s in lines[idx]) - first_size) <= 1.5
        ):
            parts.append(_line_text(lines[idx]))
            idx += 1
        return " ".join(p for p in parts if p).strip(), idx
    return "", 0


def extract_title(seg, seg_spans, xmp_data):
    # 1. Layout: the heading-sized run of lines at the top of the segment.
    title = None
    title_text, _ = _title_run(_lines(seg_spans), seg_spans)
    if title_text:
        title = _value(title_text, "text", seg.start_page, 0.85)

    # 2. Outline candidate, when we didn't get one from layout (or as
    #    corroboration).
    if seg.title:
        if title is None:
            title = _value(seg.title, "outline", seg.start_page, 0.8)
        elif seg.title.strip().lower() == (title["value"] or "").strip().lower():
            title["confidence"] = 0.95

    # 3. XMP dc:title only for a single-segment document (XMP is
    #    document-level, not per-chapter).
    dc_title = (xmp_data.get("xmp", {}).get("dc", {}) or {}).get("title")
    if title is None and dc_title:
        title = _value(dc_title.strip(), "xmp", seg.start_page, 0.6)

    if title is None:
        title = _value(None, None, None, 0.0)
    return title


# ---------------------------------------------------------------------------
# Authors + affiliations + ORCID
# ---------------------------------------------------------------------------

def _split_names(text):
    """Split an author line into raw name strings.

    Handles ', ' separators and trailing ' and '. Drops ORCID iDs,
    bracketed footnote markers, pure numeric fragments and email-like
    tokens, so that identifiers and markers do not pollute the names.
    """
    text = orcid_mod.ORCID_ID_RE.sub(" ", text or "")
    text = re.sub(r"\[\d+\]|\*\*?", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    parts = re.split(r",|\s+and\s+", text)
    names = []
    for p in parts:
        p = p.strip(" .,;")
        if not p:
            continue
        if "/" in p:  # email fragment
            continue
        if not any(ch.isalpha() for ch in p):  # pure number / marker
            continue
        names.append(p)
    return names


def _split_line(line):
    """Split a visual line into body spans and superscript markers.

    A marker is a small (relative to the line's main size) span that is
    raised above the body baseline and consists only of marker characters
    (digits, '*', '+', letters). Superscripts rendered at full size but
    raised are a known limitation of this heuristic.
    """
    line_size = max(s.size for s in line)
    body = [s for s in line if s.size >= line_size * 0.75]
    body_y0 = min((s.bbox[1] for s in body), default=line[0].bbox[1])
    body_spans, markers = [], []
    for s in line:
        if (
            s.text.strip()
            and s.size < line_size * 0.75
            # small font ascenders are short, so a raised marker does not
            # always clear the body top by much: allow 2pt of slack
            and s.bbox[1] < body_y0 + 2
            and SUPERSCRIPT_CHARS.match(s.text.strip())
        ):
            markers.append(s)
        else:
            body_spans.append(s)
    return body_spans, markers


def _assign_markers(body_spans, marker_spans):
    """Assign each superscript marker to the author span it decorates.

    A marker sits as a superscript at the end (right edge) of the name it
    belongs to, so the owning span is the one whose right edge ends just
    before the marker. A single author may own several markers (multiple
    affiliations). Returns a list parallel to ``body_spans`` of marker texts.
    """
    result = [[] for _ in body_spans]
    if not body_spans or not marker_spans:
        return result
    x1s = [s.bbox[2] for s in body_spans]
    centers = [(s.bbox[0] + s.bbox[2]) / 2 for s in body_spans]
    for mk in sorted(marker_spans, key=lambda s: s.bbox[0]):
        mk_x0 = mk.bbox[0]
        candidates = [i for i in range(len(x1s)) if x1s[i] <= mk_x0 + 5]
        if candidates:
            best = max(candidates, key=lambda i: x1s[i])
        else:
            mk_c = (mk.bbox[0] + mk.bbox[2]) / 2
            best = min(range(len(centers)), key=lambda i: abs(centers[i] - mk_c))
        result[best].append(mk.text.strip())
    return result


# Keywords that mark a line as an affiliation rather than a name or
# section heading (English/German; extend as templates require).
_AFFIL_KEYWORDS_RE = re.compile(
    r"\b(institut|institute|instituto|universit[äa]t|university|universidad|"
    r"department|fachbereich|fakult[äa]t|sektion|abteilung|center|centre|"
    r"college|school|academy|laboratory|laboratoire|zentrum|instituto)\b"
)


def _looks_like_affiliation(text):
    """True if the line text reads like an institutional affiliation."""
    return bool(_AFFIL_KEYWORDS_RE.search((text or "").lower()))


_FUNCTION_WORDS_RE = re.compile(
    r"\b(die|der|den|dem|des|und|oder|wie|von|zu|im|in|an|auf|"
    r"mit|sich|auch|eine|einen|einem|dass|diese|dieser|dieses|"
    r"the|and|or|of|to|in|on|for|with|this|that|is|are|was|were|"
    r"has|have|had|will|would|can|also|more|less|not)\b"
)


def _looks_like_prose(text):
    """True if a line of the author region looks like running body text.

    Author lines are short lists of capitalized names (with initials);
    prose contains lowercase words and function words. A single function
    word on a short line ("Joe Doe and Jane Doe") is not enough to call it
    prose. Used to stop the author region at the start of the body when
    no section heading or label is present.
    """
    words = re.findall(r"[A-Za-z\u00C0-\u024F]{2,}", text or "")
    if len(words) < 4:
        return False
    caps = sum(1 for w in words if w[:1].isupper())
    if caps / len(words) < 0.5:
        return True
    func_words = len(_FUNCTION_WORDS_RE.findall((text or "").lower()))
    # Short, mostly-capitalized lines are names; only multiple function
    # words turn them into prose. Longer lines are prose with one.
    if len(words) <= 8:
        return func_words >= 2
    return func_words >= 1


# Words that may appear between author names in a name list.
_NAME_CONNECTORS = {"and", "und", "y", "e", "et", "i", "o", "ou"}

# A name "word": letters (incl. Latin diacritics), digits, apostrophes,
# hyphens, periods (initials like "P.A.") and diacritical marks in the
# forms PDFs actually use: combining marks (U+0300-036F, "o"+U+0308)
# *and* standalone symbols (U+00A8 "¨", U+00AF, U+02DA/02DC, U+0386/7)
# which would otherwise split "Grödt" into "Gr"/"odt".
_WORD_RE = re.compile(
    r"[\w'’\-\u00A8\u00AF\u00B7\u00AD\u02C6\u02DA\u02DC\u0386\u0387\u0300-\u036f.]+"
)


def _looks_like_name_list(text):
    """Positive test: does the line read as a list of author names?

    An author line is short, built from 2-10 comma/and-separated
    fragments, and each fragment is a small number of capitalized words
    (given name(s) + surname), optionally with initials, honorifics, or
    diacritics. This is far more reliable than a negative "is this prose"
    test, which cannot distinguish a 4-name line with 'and' from a
    sentence. Pure digits (footnote markers, visible ORCID iDs) are
    ignored; a 4-digit year rejects the line (citation, not name).
    """
    text = orcid_mod.ORCID_ID_RE.sub(" ", (text or "")).strip()
    if re.search(r"(?:19|20)\d{2}", text):
        return False
    words = _WORD_RE.findall(text)
    # Letter-bearing words only; footnote digits and ORCID fragments do
    # not count towards the capitalization ratio.
    letters = [w for w in words if any(c.isalpha() for c in w)]
    if not 2 <= len(letters) <= 24:
        return False
    caps = sum(
        1 for w in letters if w[:1].isupper() or w.lower() in _NAME_CONNECTORS
    )
    if caps / len(letters) < 0.75:
        return False
    # No long tokens: names are short words, not sentence fragments.
    if max(len(w) for w in letters) > 20:
        return False
    # Split into fragments and check their shape: 1-5 letter-words each,
    # each fragment ending in an uppercase-starting (surname) word.
    fragments = re.split(r",|\s+(?:and|und)\s+", text)
    fragments = [f.strip() for f in fragments if f.strip()]
    if not 1 <= len(fragments) <= 10:
        return False
    for frag in fragments:
        fw = [
            w
            for w in _WORD_RE.findall(frag)
            if any(c.isalpha() for c in w)
            and w.lower() not in _NAME_CONNECTORS
        ]
        # A fragment with no letter-bearing words is a footnote number or
        # a trailing ORCID iD, not a name; it does not invalidate the list.
        if not fw:
            continue
        if len(fw) > 5:
            return False
        if not fw[-1].lstrip(".\u0300-\u036f")[:1].isupper():
            return False
    return True


def _column_geometry(lines):
    """Detect a two-column layout from dense left-edge (x0) clusters.

    Returns ``(left_x0, right_x0, n_columns)`` where ``right_x0`` is the
    left edge of the second column (None for single-column layouts).
    """
    x0c = Counter()
    for line in lines:
        if not line:
            continue
        x0c[round(min(s.bbox[0] for s in line))] += 1
    clusters = sorted(x for x, c in x0c.items() if c >= 8)
    if len(clusters) >= 2 and clusters[1] - clusters[0] > 100:
        return clusters[0], clusters[1], 2
    left = clusters[0] if clusters else 0
    return left, None, 1


# Section heading labels in the languages this project deals with,
# used to recognise numbered headings such as "1. Einleitung".
_HEADING_WORDS_RE = re.compile(
    r"\b(introduction|einleitung|introducci[oó]n|introduzione|"
    r"definitions?|definitionen|method|methods?|methodik|material|"
    r"results?|ergebnisse|discussion|diskussion|konklusion|conclusion|"
    r"schlu[ßs]folgerung|litteratur|literatur|references|bibliography|"
    r"anhang|appendix|zusammenfassung|summary|res[uü]me|acknowledg)\b"
)


def _heading_text_of(line):
    """The heading text of a line, or None.

    In multi-column layouts a visual line may contain text from two
    columns, so the candidates are the individual span texts; the
    longest span that starts with a section number is the heading.
    """
    best = None
    for s in line:
        t = s.text.strip()
        if re.match(
            r"^(?:\(?\d{1,2}\)?[.)]|[IVX]{1,4}\.)\s*\S", t
        ) and (best is None or len(t) > len(best)):
            best = t
    return best


def _looks_like_section_heading(line):
    """True if a line (or one of its spans) is a numbered section heading
    ("1. Einleitung", "2 Definition der ...", "(1) Results").

    A heading is short, starts with a number (with or without a
    following dot/parenthesis), and either contains a known section
    keyword or stays under ~8 words. Lines that read like institutional
    affiliations are never treated as headings.
    """
    text = _heading_text_of(line)
    if not text:
        return False
    if _looks_like_affiliation(text):
        return False
    # Arabic numeral ("1. Einleitung") or Roman numeral ("I. INTRODUCTION").
    m = re.match(
        r"^(?:\(?\d{1,2}\)?|[IVX]{1,4})[.)]?\s+([A-ZÄÖÜ][\w'’\- .,&;:])*$",
        text,
    )
    if not m:
        return False
    rest = m.group(1).strip()
    words = re.findall(r"[\w'’\-]+", rest)
    if not words:
        return False
    if _HEADING_WORDS_RE.search(rest.lower()):
        return True
    # Numbered line of a few capitalized words = heading candidate.
    if len(words) <= 8 and sum(1 for w in words if w[:1].isupper()) / len(words) >= 0.6:
        return True
    return False


def _parse_affiliation_list(lines):
    """Parse a numbered affiliation list into ``{number: text}``.

    Journal templates render affiliations either one-per-line
    ("1. Institute ...") or as a *single flowing list* that wraps across
    lines, with subsequent entries mid-line:
    "1. Oakwood Institute of Applied Sciences,
     2. Brightwater Consultants, 3. Northwind Research."

    The list is collected line by line: it starts at the first line
    beginning with "N." / "N)" and continues over lines that carry a
    further "N." marker (the wrapping case). The joined text is then
    split at every "N. " / "N)" marker, so both layouts work.

    Returns ``(affiliations, line_positions)`` where ``line_positions``
    are the indices (into ``lines``) of the lines that belong to the
    list, so the caller can exclude them from the author-name region.
    """
    collected_idx = []
    started = False
    # A numbered affiliation entry starts with "N." / "N)" or with a
    # number followed by a wide gap ("1  Institute ...").
    entry_re = re.compile(r"\d{1,2}(?:[.)]|\s{2,})")
    for i, line in enumerate(lines):
        text = _line_text(line)
        if not text:
            continue
        if _looks_like_section_heading(line):
            break  # body has started
        if not started:
            if entry_re.match(text):
                started = True
                collected_idx.append(i)
            continue
        if entry_re.match(text) or entry_re.search(text):
            collected_idx.append(i)
        else:
            break  # section label / free text: the list is over

    blob = " ".join(_line_text(lines[i]) for i in collected_idx)
    affiliations = {}
    matches = list(re.finditer(r"(?:^|[\s,])\d{1,2}(?:[.)]|\s{2,})", blob))
    for i, m in enumerate(matches):
        num = int(m.group(0).strip().rstrip(".)"))
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(blob)
        text = blob[start:end].strip().rstrip(".,;").strip()
        if text:
            affiliations[num] = text
    return affiliations, set(collected_idx)


# Maximum number of lines the author region may span before it is
# clearly bleeding into the body (safety net for templates where the
# body starts without any heading or label).
_MAX_AUTHOR_REGION_LINES = 10

# A horizontal gap between two spans larger than this (in PDF points)
# starts a new author column in a multi-column author grid.
_AUTHOR_GRID_GAP = 20.0


def _author_columns(name_line):
    """Split a name line into column groups by large horizontal gaps.

    Multi-column authors are placed side-by-side with no separators
    (no commas / "and"): "Joe Doe  Jane Doe  Jack Smith  Jill Smith".
    The only cue is a large x-gap between the columns
    (a space is ~4pt, a column gap is >20pt). Whitespace spans and
    superscript markers (raised single digits/letters that are not part
    of a name) are ignored, so a footnote marker after a single author
    is not mistaken for a second column.
    """
    line_size = max((s.size for s in name_line if s.text.strip()), default=11.0)
    columns = []
    current = []
    prev_x1 = None
    for s in name_line:
        if not s.text.strip():
            continue
        # Skip superscript markers: no letters, and well below the line size.
        if s.size < line_size * 0.75 and not any(c.isalpha() for c in s.text):
            continue
        if current and s.bbox[0] - prev_x1 > _AUTHOR_GRID_GAP:
            columns.append(current)
            current = []
        current.append(s)
        prev_x1 = s.bbox[2]
    if current:
        columns.append(current)
    return columns


def _looks_like_author_grid(region):
    """True if the author region begins with a multi-column author grid.

    A grid has >=2 columns on its first line and a following line that is
    not a name list (affiliation / email / address text).
    """
    if len(region) < 2:
        return False
    if len(_author_columns(region[0])) < 2:
        return False
    return True


def _author_grid_authors(region):
    """Extract authors from a multi-column author grid.

    The first line holds the names (one per column); the following lines
    hold each author's affiliation and email, stacked per column (the
    affiliation may itself span several lines). A span is assigned to a
    column by the nearest column anchor (the column's leftmost name x).
    Emails (spans containing "@") are captured per column; everything
    else on those lines is affiliation text.

    Returns a list of author dicts in the same shape used elsewhere.
    """
    columns = _author_columns(region[0])
    anchors = [min(s.bbox[0] for s in col) for col in columns]

    def col_index(x):
        return min(range(len(anchors)), key=lambda i: abs(anchors[i] - x))

    # Build per-column output.
    names = []
    for col in columns:
        names.append(
            _normalize_text(
                " ".join(s.text for s in col).strip(" .,;:")
            )
        )

    affil_buffers = [[] for _ in columns]
    emails = [None] * len(columns)
    for line in region[1:]:
        # Group this line's spans by column.
        per_col = [[] for _ in columns]
        for s in line:
            if not s.text.strip():
                continue
            per_col[col_index(s.bbox[0])].append(s)
        for ci, spans in enumerate(per_col):
            if not spans:
                continue
            frag = " ".join(s.text for s in spans).strip()
            if "@" in frag and emails[ci] is None:
                emails[ci] = frag
            else:
                affil_buffers[ci].append(frag)

    page = region[0][0].page if region[0] else 0
    authors = []
    for ci in range(len(columns)):
        name = names[ci]
        if not name:
            continue
        affil_text = " ".join(
            a for a in affil_buffers[ci] if a
        ).strip()
        authors.append(
            {
                "order": ci + 1,
                "name": _value(name, "text", page, 0.85),
                "affiliations": [
                    _value(affil_text, "text", page, 0.7)
                ]
                if affil_text
                else [],
                "orcid": _value(None, None, page, 0.0),
                "email": _value(emails[ci], "text", page, 0.9)
                if emails[ci]
                else None,
            }
        )
    return authors


def _author_fragments(body_spans):
    """Group the body spans of an author line into name fragments.

    The spans (already in left-to-right order) are tokenized; a fragment
    runs until a separator (",", ";", "&", connector words like "and")
    or a non-letter token (footnote number, visible ORCID iD) ends it.
    This yields one fragment per author even when the first and last
    name are separate spans ("Joe" / "Doe") or when the template
    mixes both ("J. Doe").

    Returns a list of ``{"words": [...], "spans": [indices]}``.
    """
    text = "".join(s.text for s in body_spans)
    ranges = []
    pos = 0
    for i, s in enumerate(body_spans):
        ranges.append((pos, pos + len(s.text), i))
        pos += len(s.text)

    def span_of(p):
        for a, b, i in ranges:
            if a <= p < b:
                return i
        return ranges[-1][2] if ranges else 0

    fragments = []
    current = []
    for m in re.finditer(
        r"\b(?:and|und|et|y|e)\b|" + _WORD_RE.pattern + r"|[,;:&]+", text
    ):
        tok = m.group(0)
        if tok.lower() in _NAME_CONNECTORS or re.fullmatch(r"[,;:&]+", tok):
            if current:
                fragments.append(current)
                current = []
            continue
        if not any(c.isalpha() for c in tok):
            # Footnote number / visible ORCID iD: separator, not a name.
            continue
        cleaned = orcid_mod.ORCID_ID_RE.sub("", tok).strip(" .,;:()")
        if cleaned:
            current.append((cleaned, span_of(m.start())))
    if current:
        fragments.append(current)

    result = []
    for frag in fragments:
        frag = [(w.strip(" .,;:()"), i) for w, i in frag]
        frag = [(w, i) for w, i in frag if w]
        if not frag:
            continue
        # Deduplicate span indices (several words may come from the same
        # span, e.g. "P.A. Jensen"), preserving order.
        seen = []
        for w, i in frag:
            if i not in seen:
                seen.append(i)
        result.append({"words": [w for w, i in frag], "spans": seen})
    return result


def extract_authors(seg, seg_spans, links):
    """Extract author entries with affiliations and ORCID iDs.

    Heuristic: the author region is the block of lines between the title
    line and the first known section label (abstract / keywords). Each
    line in that region that looks like a name list yields one or more
    authors; superscript markers on the line are mapped to the numbered
    affiliation list that follows the author block.
    """
    lines = _lines(seg_spans)
    if not lines:
        return []

    # The title run is the heading-sized lines at the top; authors start
    # right after it.
    _, start_idx = _title_run(lines, seg_spans)

    # Bound the author region: it ends at the first of
    #   * a known section label (Abstract / Keywords ...),
    #   * a numbered section heading ("1. Einleitung") — the body starts,
    #   * a vertical safety cap (author blocks are short; anything past
    #     this point is body text even without a heading),
    #   * the next page.
    abs_idx, _, _ = _find_label(lines, ABSTRACT_LABELS)
    kw_idx, _, _ = _find_label(lines, KEYWORD_LABELS)
    end_idx = len(lines)
    for idx in (i for i in (abs_idx, kw_idx) if i is not None):
        end_idx = min(end_idx, idx)
    for i in range(start_idx, min(len(lines), start_idx + 40)):
        line = lines[i]
        if not line:
            continue
        if line[0].page != lines[start_idx][0].page:
            end_idx = min(end_idx, i)
            break
        if _looks_like_section_heading(line):
            end_idx = min(end_idx, i)
            break
    end_idx = min(end_idx, start_idx + _MAX_AUTHOR_REGION_LINES)

    region = lines[start_idx:end_idx]
    if not region:
        return []

    # Multi-column author grid: authors side-by-side with no separators,
    # each with its own affiliation/email column below. Detect it before
    # the name-list path (which would reject the single-collapsed line).
    if _looks_like_author_grid(region):
        return _author_grid_authors(region)

    # Parse the affiliation list over the region (plus a small window past
    # the label in case it trails slightly). The returned set holds the
    # relative indices of lines that belong to the affiliation list, so
    # they are excluded from the author-name pass below.
    affiliations, affil_rel = _parse_affiliation_list(
        lines[start_idx: min(len(lines), end_idx + 10)]
    )

    page_links = [l for l in links if seg.start_page <= l.page < seg.end_page]

    authors = []
    order = 1
    for rel, line in enumerate(region):
        if rel in affil_rel:
            continue  # this line is part of the affiliation list
        body_spans, marker_spans = _split_line(line)
        if not body_spans:
            continue
        text = " ".join(s.text for s in body_spans)
        if not text.strip():
            continue
        # Skip lines that are clearly affiliations rather than names.
        if _looks_like_affiliation(text):
            continue
        # Positive test: the line must actually read as a list of author
        # names. Body text, stray citation references in the introduction
        # and conference headers are all rejected here.
        if not _looks_like_name_list(text):
            continue

        fragments = _author_fragments(body_spans)
        if not fragments:
            continue

        # mailto: links on this line -> correspondence author + email
        email = None
        for link in page_links:
            m = MAILTO_RE.match(link.uri)
            if m and abs(link.rect[1] - line[0].baseline) < 10:
                email = m.group(1)
                break

        span_markers = _assign_markers(body_spans, marker_spans)
        line_text = " ".join(s.text for s in line)
        for frag in fragments:
            name = _normalize_text(
                re.sub(r"\s+", " ", " ".join(frag["words"]).strip(" .,;"))
            )
            if not name:
                continue
            first_span = body_spans[frag["spans"][0]]
            last_span = body_spans[frag["spans"][-1]]
            # The fragment owns the markers decorating any of its spans.
            mk_list = [mk for i in frag["spans"] for mk in span_markers[i]]
            # An ORCID icon sits at the end of a name; join from the
            # fragment's last span.
            orcid, orcid_source = orcid_mod.resolve(
                last_span, page_links, line_text=line_text
            )
            authors.append(
                {
                    "order": order,
                    "name": _value(name, "text", first_span.page, 0.8),
                    "affiliations": [
                        _value(affiliations[int(mk)], "text", None, 0.6)
                        for mk in mk_list
                        if mk.isdigit() and int(mk) in affiliations
                    ],
                    "orcid": _value(
                        orcid, orcid_source or None, first_span.page,
                        0.95 if orcid_source == "annotation" else 0.7,
                    ),
                    "email": _value(email, "link", first_span.page, 0.9)
                    if email
                    else None,
                }
            )
            order += 1
    return authors


# ---------------------------------------------------------------------------
# Abstract
# ---------------------------------------------------------------------------

def extract_abstract(seg, seg_spans):
    lines = _lines(seg_spans)
    idx, label, rest = _find_label(lines, ABSTRACT_LABELS)
    if idx is None:
        return _value(None, None, None, 0.0)

    # The abstract text starts on the label line (after "Abstract:") and
    # runs until the next known section label.
    end_idx = len(lines)
    for labels in (KEYWORD_LABELS, REFERENCE_LABELS):
        i, _, _ = _find_label(lines, labels, start=idx + 1)
        if i is not None:
            end_idx = min(end_idx, i)

    parts = []
    if rest:
        parts.append(rest)
    for line in lines[idx + 1:end_idx]:
        parts.append(_line_text(line))
    text = "\n".join(p for p in parts if p).strip()
    if not text:
        return _value(None, None, None, 0.0)
    return _value(text, "text", lines[idx][0].page if lines[idx] else None, 0.75)


# ---------------------------------------------------------------------------
# Keywords
# ---------------------------------------------------------------------------

def extract_keywords(seg, seg_spans):
    lines = _lines(seg_spans)
    idx, label, rest = _find_label(lines, KEYWORD_LABELS)
    if idx is None:
        return []
    # The label line may carry the keywords inline ("Keywords: a, b, ...").
    text = rest
    if not text:
        # look at the next few lines for an inline list
        for line in lines[idx + 1: idx + 3]:
            t = _line_text(line)
            if t and not any(
                t.lower().strip().rstrip(":").endswith(l)
                for l in ABSTRACT_LABELS + REFERENCE_LABELS
            ):
                text = t
                break
    if not text:
        return []
    items = [k.strip() for k in re.split(r"[;,]|;\s*", text) if k.strip()]
    return [
        _value(k, "text", lines[idx][0].page if lines[idx] else None, 0.8)
        for k in items
    ]


# ---------------------------------------------------------------------------
# Citations / references
# ---------------------------------------------------------------------------

DOI_LINK_RE = re.compile(r"(?:dx\.)?doi\.org/(10\.\d{4,9}/\S+)", re.I)


def _references_heading(lines):
    for i, line in enumerate(lines):
        text = _line_text(line).strip().rstrip(":").strip().lower()
        if text in REFERENCE_LABELS:
            return i
    return None


def _split_citation_entries(lines, start_idx):
    """Split reference lines into entries on numbered markers or hanging indent.

    A new entry starts on a line that begins with 'n]' / 'n.' / '(n)' where
    n continues the previous number.
    """
    entries = []
    current = []
    last_num = 0
    for line in lines[start_idx:]:
        text = _line_text(line)
        m = re.match(r"^\s*\[?(\d{1,3})\]?[.)]?\s+(.*)", text)
        if m and int(m.group(1)) == last_num + 1:
            if current:
                entries.append(current)
            current = [line]
            last_num = int(m.group(1))
        elif current:
            current.append(line)
        elif text.strip():
            current = [line]  # unnumbered list: each line is one entry
            entries.append(current)
            current = []
    if current:
        entries.append(current)
    return entries


def extract_citations(seg, seg_spans, links):
    lines = _lines(seg_spans)
    ref_idx = _references_heading(lines)
    if ref_idx is None:
        return []
    page_links = [l for l in links if seg.start_page <= l.page < seg.end_page]

    citations = []
    for entry in _split_citation_entries(lines, ref_idx + 1):
        raw = " ".join(_line_text(l) for l in entry)
        raw = re.sub(r"^\s*\[?\d{1,3}\]?[.)]?\s*", "", raw).strip()
        if not raw:
            continue
        first_span = entry[0][0]

        # DOI: text first, then link annotations on the same page.
        doi = None
        doi_source = None
        m = DOI_TEXT_RE.search(raw)
        if m:
            doi, doi_source = m.group(0).rstrip(".,;"), "text"
        if not doi:
            for link in page_links:
                if link.page != first_span.page:
                    continue
                dm = DOI_LINK_RE.search(link.uri)
                if dm:
                    doi, doi_source = dm.group(1).rstrip(".,;"), "link"
                    break

        citations.append(
            {
                "raw": _value(raw, "text", first_span.page, 0.6),
                "doi": _value(doi, doi_source, first_span.page,
                              0.9 if doi_source == "link" else 0.7)
                if doi
                else None,
                "authors": _value(None, None, None, 0.0),
                "year": _value(None, None, None, 0.0),
                "title": _value(None, None, None, 0.0),
                "venue": _value(None, None, None, 0.0),
            }
        )
    return citations


# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------

def extract_all(seg, spans, links, xmp_data):
    """Extract all fields for one segment, each provenance-tagged."""
    seg_spans = _segment_spans(seg, spans)
    return {
        "title": extract_title(seg, seg_spans, xmp_data),
        "authors": extract_authors(seg, seg_spans, links),
        "abstract": extract_abstract(seg, seg_spans),
        "keywords": extract_keywords(seg, seg_spans),
        "citations": extract_citations(seg, seg_spans, links),
        "pages": seg.page_range,
    }
