"""
PDF metadata ingestion for tuw_backcontent.

Extracts per-article metadata (title, authors with affiliations and
ORCID iDs, abstract, keywords, citations) from a completed PDF,
combining the text layer with the structural PDF layers (outline, link
annotations, XMP) so that information only reachable via annotations
(e.g. ORCID iDs stored on an ORCID icon's link) is captured as well.

Public entry point: :func:`run`.
"""

from .pipeline import run  # noqa: F401
from .extract import IngestError  # noqa: F401
