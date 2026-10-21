import os

from django.conf import settings
from django.core.management.base import BaseCommand

from journal import models
from utils import tuw_journal_export


class Command(BaseCommand):
    """Exports a complete journal (data + files) into a portable bundle."""

    help = (
        "Exports a journal's complete state (records, settings and binary "
        "files) into a bundle directory that can be imported with "
        "tuw_import_journal on another installation."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "journal_code",
            help="Code of the journal to export",
        )
        parser.add_argument(
            "-o",
            "--output",
            default=os.path.join(settings.BASE_DIR, "bundles"),
            help=(
                "Output directory for the bundle (default: "
                "<BASE_DIR>/bundles). A <code>-<timestamp>/ subdirectory is "
                "created inside it."
            ),
        )
        parser.add_argument(
            "-n",
            "--no-binaries",
            action="store_true",
            help="Do not copy binary files into the bundle (data only).",
        )
        parser.add_argument(
            "--no-article-access",
            action="store_true",
            help=(
                "Do not export article access metrics (the per-event "
                "ArticleAccess log and the HistoricArticleAccess COUNTER "
                "aggregates), which can make up the bulk of a bundle."
            ),
        )
        parser.add_argument(
            "-q",
            "--quiet",
            action="store_true",
            help="Suppress progress output.",
        )

    def handle(self, *args, **options):
        journal_code = options["journal_code"]
        try:
            journal = models.Journal.objects.get(code=journal_code)
        except models.Journal.DoesNotExist:
            self.stderr.write(
                "No journal with code '{}' found.".format(journal_code)
            )
            return

        summary = tuw_journal_export.export_bundle(
            journal,
            options["output"],
            include_binaries=not options["no_binaries"],
            verbose=not options["quiet"],
            include_article_access=not options["no_article_access"],
        )
        self.stdout.write(
            "Exported journal '{}' to {}".format(
                journal_code, summary["bundle_dir"]
            )
        )
