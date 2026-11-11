from django.core.management.base import BaseCommand

from utils import tuw_journal_export


class Command(BaseCommand):
    """Imports a journal bundle created by tuw_export_journal."""

    help = (
        "Imports a journal bundle created by tuw_export_journal into this "
        "installation. The journal is created with the same code unless "
        "--code is given."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "bundle_dir",
            help=(
                "Path to the bundle directory (the directory containing "
                "journal.json and files/)"
            ),
        )
        parser.add_argument(
            "-c",
            "--code",
            default=None,
            help="Use this journal code instead of the exported one.",
        )
        parser.add_argument(
            "-d",
            "--domain",
            default=None,
            help="Use this primary domain instead of the exported one.",
        )
        parser.add_argument(
            "-q",
            "--quiet",
            action="store_true",
            help="Suppress progress output.",
        )

    def handle(self, *args, **options):
        journal = tuw_journal_export.import_bundle(
            options["bundle_dir"],
            code=options["code"],
            domain=options["domain"],
            verbose=not options["quiet"],
        )
        self.stdout.write(
            "Imported journal '{}' (pk {})" .format(journal.code, journal.pk)
        )
