"""
Optional network enrichment (disabled by default).

* Authors with an ORCID iD are checked against the ORCID lookup service
  (the TUW library proxy used elsewhere in this codebase). A failing
  lookup never raises; it only downgrades the value's confidence and
  records a warning.
* Citations with a DOI are resolved through Crossref to fill in
  authors/year/title/venue. Local values always win over remote ones:
  enrichment fills gaps, never overwrites.
"""

import logging

import requests

logger = logging.getLogger(__name__)

# Same proxy endpoints as tuw_backcontent.views (backcontent_author_search).
ORCID_DIRECT_URL = "https://www2.ub.tuwien.ac.at/orcid/"
CROSSREF_WORKS_URL = "https://api.crossref.org/works/"
TIMEOUT = 10


def _get_json(url, params=None):
    try:
        resp = requests.get(url, params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("ingest enrich: lookup at %s failed: %s", url, exc)
        return None


def _enrich_author(author, warnings):
    orcid_field = author.get("orcid")
    if not orcid_field or not orcid_field.get("value"):
        return
    orcid_id = orcid_field["value"]

    data = _get_json(ORCID_DIRECT_URL + orcid_id)
    if data is None:
        # Unreachable: keep the value but flag it for review.
        warnings.append(
            "ORCID %s could not be verified (lookup failed)" % orcid_id
        )
        orcid_field["confidence"] = min(orcid_field["confidence"], 0.5)
        return

    # The direct endpoint returns the record with the search shape.
    name_entity = data.get("preferredNameEntityForThePerson") or {}
    forename = name_entity.get("forename", "")
    surname = name_entity.get("surname", "")

    # Name sanity check: surname (or forename) of the extracted name should
    # appear in the ORCID record, else flag a possible mis-join.
    extracted = (author.get("name") or {}).get("value") or ""
    extracted_lower = extracted.lower()
    if (surname and surname.lower() not in extracted_lower) and (
        forename and forename.lower() not in extracted_lower
    ):
        warnings.append(
            "ORCID %s record name '%s %s' does not match extracted author "
            "'%s' - check the join" % (orcid_id, forename, surname, extracted)
        )
        orcid_field["confidence"] = min(orcid_field["confidence"], 0.5)
    else:
        orcid_field["confidence"] = max(orcid_field["confidence"], 0.95)

    # Fill a missing first affiliation from the ORCID employment/education.
    affiliations = author.get("affiliations") or []
    if not affiliations:
        names = []
        aff = data.get("affiliation") or {}
        for key in ("emp", "edu"):
            for value in aff.get(key, []) or []:
                if value and value not in names:
                    names.append(value)
        if names:
            author["affiliations"] = [
                {
                    "value": names[0],
                    "source": "orcid_api",
                    "page": None,
                    "confidence": 0.7,
                }
            ]


def _enrich_citation(citation, warnings):
    doi_field = citation.get("doi")
    if not doi_field or not doi_field.get("value"):
        return
    data = _get_json(CROSSREF_WORKS_URL + doi_field["value"])
    if not isinstance(data, dict):
        return  # leave as-is; DOI already has provenance

    message = data.get("message", data)

    year = None
    for key in ("issued", "created", "published-print", "published-online"):
        date_parts = (message.get(key) or {}).get("date-parts") or []
        if date_parts and date_parts[0]:
            year = str(date_parts[0][0])
            break

    title = (message.get("title") or [None])[0]
    venue = (message.get("container-title") or [None])[0]

    authors = []
    for item in message.get("author", []) or []:
        given = item.get("given", "")
        family = item.get("family", "")
        name = ("%s %s" % (given, family)).strip()
        if name:
            authors.append(name)

    def _fill(field_key, value):
        field = citation.get(field_key)
        if field and not field.get("value") and value:
            field["value"] = value
            field["source"] = "crossref"
            field["confidence"] = 0.85

    if authors:
        _fill("authors", ", ".join(authors))
    if year:
        _fill("year", year)
    if title:
        _fill("title", title)
    if venue:
        _fill("venue", venue)


def enrich(artifact):
    """Enrich a single segment dict in place and return it.

    :param artifact: the dict produced by
        :func:`tuw_backcontent.ingest.fields.extract_all`.
    """
    warnings = []
    for author in artifact.get("authors", []):
        _enrich_author(author, warnings)
    for citation in artifact.get("citations", []):
        _enrich_citation(citation, warnings)
    if warnings:
        artifact["warnings"] = warnings
    return artifact
