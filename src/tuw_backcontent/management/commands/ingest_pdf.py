"""
Management command: extract metadata from a PDF.

Usage:
    python src/manage.py ingest_pdf /path/to/doc.pdf --dry-run
    python src/manage.py ingest_pdf /path/to/doc.pdf --article 42
    python src/manage.py ingest_pdf /path/to/doc.pdf --article 42 --enrich

Without ``--article`` the extracted artifact is printed as JSON (the
default, safe behaviour). With ``--article`` the first segment is applied
to the given Article (title, abstract, keywords, authors).
"""

import json

from django.core.management.base import BaseCommand, CommandError

from tuw_backcontent.ingest import run, IngestError
from submission import models as submission_models
from core import models as core_models


def _unwrap(field):
    """Return the plain value of a provenance dict, or None."""
    if not field:
        return None
    value = field.get("value")
    return value if value not in (None, "") else None


def _split_name(full_name):
    """Crude split of 'Forename Surname' -> (first, last).

    Multi-word given names are not reliably distinguishable from
    two-part surnames without an external check; everything before the
    final word is treated as first name.
    """
    parts = (full_name or "").strip().split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return "", parts[0]
    return " ".join(parts[:-1]), parts[-1]


def _flag_low_confidence(article_dict):
    """Collect (path, value) pairs whose confidence is below the review bar."""
    flagged = []
    title = article_dict.get("title") or {}
    if title.get("value") and title.get("confidence", 0) < 0.7:
        flagged.append(("title", title["value"]))
    abstract = article_dict.get("abstract") or {}
    if abstract.get("value") and abstract.get("confidence", 0) < 0.6:
        flagged.append(("abstract", "(see JSON)"))
    for i, author in enumerate(article_dict.get("authors", [])):
        orcid_field = author.get("orcid") or {}
        if orcid_field.get("value") and orcid_field.get("confidence", 0) < 0.7:
            flagged.append(
                ("authors[%d].orcid" % i, orcid_field["value"])
            )
    return flagged


def apply_to_article(result, article_id):
    """Apply the first segment of ``result`` to the given Article.

    Reuses existing models only (no migrations): Article.title/abstract,
    Keyword/KeywordArticle, FrozenAuthor, ControlledAffiliation.
    Returns a summary dict for the console output.
    """
    from django.utils import timezone

    article = submission_models.Article.objects.get(pk=article_id)
    art = result["articles"][0]
    summary = {"article_id": article.pk, "authors_created": 0, "warnings": []}

    title = _unwrap(art.get("title"))
    if title:
        article.title = title
    abstract = _unwrap(art.get("abstract"))
    if abstract:
        article.abstract = abstract
    if not article.date_accepted:
        article.date_accepted = timezone.now()
    article.save()

    # Keywords (ordered M2M through KeywordArticle).
    keywords = [
        _unwrap(k) for k in art.get("keywords", [])
    ]
    keywords = [k for k in keywords if k]
    if keywords:
        for word in keywords:
            keyword, _ = submission_models.Keyword.objects.get_or_create(
                word=word
            )
            exists = submission_models.KeywordArticle.objects.filter(
                article=article, keyword=keyword
            ).exists()
            if not exists:
                submission_models.KeywordArticle.objects.create(
                    article=article, keyword=keyword
                )
        summary["keywords"] = keywords

    # Authors -> FrozenAuthor (+ first affiliation, ORCID, email).
    existing = {
        (a.last_name or "").lower(): a
        for a in submission_models.FrozenAuthor.objects.filter(article=article)
    }
    for author in art.get("authors", []):
        full_name = _unwrap(author.get("name"))
        if not full_name:
            continue
        first, last = _split_name(full_name)
        orcid = _unwrap(author.get("orcid"))
        email = _unwrap(author.get("email"))
        affil_values = [
            _unwrap(a) for a in author.get("affiliations", [])
        ]
        affil_values = [a for a in affil_values if a]

        fa = existing.get(last.lower())
        created = False
        if not fa:
            fa = submission_models.FrozenAuthor(
                article=article,
                first_name=first,
                last_name=last,
                order=article.next_frozen_author_order(),
            )
            created = True
        if orcid and not fa.frozen_orcid:
            fa.frozen_orcid = orcid
        if email and not fa.frozen_email:
            fa.frozen_email = email
        fa.save()
        existing[fa.last_name.lower()] = fa
        summary["authors_created"] += 1 if created else 0

        if affil_values:
            core_models.ControlledAffiliation.get_or_create_without_ror(
                institution=affil_values[0],
                frozen_author=fa,
            )

    summary["warnings"] = _flag_low_confidence(art)
    return summary


class Command(BaseCommand):
    help = (
        "Extract metadata (title, authors, affiliations, ORCID iDs, abstract, "
        "keywords, citations) from a PDF. Prints a provenance-tagged JSON "
        "artifact by default; applies the first segment to an Article with "
        "--article."
    )

    def add_arguments(self, parser):
        parser.add_argument("path", help="Path to the PDF file")
        parser.add_argument(
            "--article",
            type=int,
            default=None,
            help="Apply the result to this Article id",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only print the JSON artifact (default without --article)",
        )
        parser.add_argument(
            "--enrich",
            action="store_true",
            help=(
                "Enable network enrichment (ORCID verification, Crossref "
                "DOI resolution); off by default"
            ),
        )

    def handle(self, path, *args, **opts):
        if opts["dry_run"] and opts["article"]:
            raise CommandError(
                "--dry-run and --article are mutually exclusive."
            )
        try:
            result = run(path, enrich_=opts["enrich"])
        except IngestError as exc:
            raise CommandError(str(exc))
        except Exception as exc:
            raise CommandError("Could not process %s: %s" % (path, exc))

        if opts["article"]:
            summary = apply_to_article(result, opts["article"])
            self.stdout.write(
                self.style.SUCCESS(
                    "Applied to article %s: %d author(s) created."
                    % (summary["article_id"], summary["authors_created"])
                )
            )
            if summary.get("warnings"):
                self.stdout.write(
                    self.style.WARNING(
                        "Low-confidence values for manual review:\n  %s"
                        % "\n  ".join(
                            "%s = %r" % (p, v) for p, v in summary["warnings"]
                        )
                    )
                )
            return

        # Default / --dry-run: print the artifact.
        self.stdout.write(json.dumps(result, indent=2, ensure_ascii=False))
