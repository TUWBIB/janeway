"""Creates a core.Account for a detached FrozenAuthor and links them.

Usage:
    manage.py tuw_create_account_from_frozen_author <frozen_email> [options]

Example:
    manage.py tuw_create_account_from_frozen_author "jane.doe@example.com"

Notes:
- The FrozenAuthor is looked up by its ``frozen_email`` (case-insensitive).
  If no detached record carries that email, a record whose ORCID matches
  an account's email is also tried via ``--orcid``.
- If an Account already exists for that email, it is reused (no new account
  is created) and the frozen author is simply linked to it.
- Linking mirrors ``FrozenAuthor.associate_with_account()``: the frozen
  author's ``author`` FK is set and ``frozen_email`` is cleared.
- The new account receives the 'author' role for the article's journal (if
  the role exists), is activated, and the frozen author's ORCID is copied
  to the account.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core import models as core_models
from submission import models as submission_models


class Command(BaseCommand):
    help = (
        "Creates a core.Account for a frozen author identified by "
        "frozen_email (and links the frozen author to the new account)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "frozen_email",
            help="Email stored on the detached FrozenAuthor (frozen_email).",
        )
        parser.add_argument(
            "--orcid",
            default=None,
            help=(
                "ORCID to use if the frozen author has none stored. "
                "Copied to the new account."
            ),
        )
        parser.add_argument(
            "--first-name",
            default=None,
            help="Override the first name taken from the frozen author.",
        )
        parser.add_argument(
            "--last-name",
            default=None,
            help="Override the last name taken from the frozen author.",
        )
        parser.add_argument(
            "--inactive",
            action="store_true",
            default=False,
            help="Leave the new account inactive (default: active).",
        )
        parser.add_argument(
            "--no-role",
            action="store_true",
            default=False,
            help="Do not assign the 'author' role for the article's journal.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Show what would happen without changing anything.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        frozen_email = options["frozen_email"].strip()

        # --- find the frozen author ------------------------------------
        fqs = submission_models.FrozenAuthor.objects.filter(
            frozen_email__iexact=frozen_email
        )
        if not fqs.exists():
            orcid = options["orcid"]
            if orcid:
                fqs = submission_models.FrozenAuthor.objects.filter(
                    frozen_orcid=orcid
                )
        if not fqs.exists():
            raise CommandError(
                "No FrozenAuthor found with frozen_email %r%s."
                % (
                    frozen_email,
                    " (or frozen_orcid %r)" % options["orcid"]
                    if options["orcid"]
                    else "",
                )
            )

        frozen_author = fqs.order_by("pk").first()
        more = fqs.count() - 1
        if frozen_author.author:
            raise CommandError(
                "FrozenAuthor %s (%s) is already linked to account %r; "
                "nothing to do."
                % (
                    frozen_author.pk,
                    frozen_author.full_name(),
                    frozen_author.author.email,
                )
            )
        if more:
            self.stdout.write(
                self.style.WARNING(
                    "Found %d frozen authors with that email; using pk=%s (%s)."
                    % (
                        fqs.count(),
                        frozen_author.pk,
                        frozen_author.full_name(),
                    )
                )
            )

        journal = frozen_author.article.journal if frozen_author.article else None
        orcid = frozen_author.frozen_orcid or options["orcid"] or ""

        self.stdout.write(
            "Frozen author pk=%s %s | email=%s | orcid=%s | journal=%s"
            % (
                frozen_author.pk,
                frozen_author.full_name(),
                frozen_email,
                orcid or "-",
                journal.code if journal else "-",
            )
        )

        # --- find or create the account --------------------------------
        account = core_models.Account.objects.filter(
            email__iexact=frozen_email
        ).first()
        if account:
            self.stdout.write(
                "Reusing existing account pk=%s (%s)."
                % (account.pk, account.email)
            )
        else:
            first_name = options["first_name"] or frozen_author.first_name or ""
            last_name = options["last_name"] or frozen_author.last_name or ""
            if not (first_name or last_name):
                # Account.first_name / last_name are required.
                first_name = first_name or "Author"
                last_name = last_name or frozen_email.split("@")[0]

            if options["dry_run"]:
                self.stdout.write(
                    self.style.MIGRATE_HEADING(
                        "[dry-run] Would create account %s %s <%s> "
                        "(active=%s)."
                        % (
                            first_name,
                            last_name,
                            frozen_email,
                            not options["inactive"],
                        )
                    )
                )
                return

            account = core_models.Account.objects.create(
                email=frozen_email,
                username=frozen_email.lower(),
                first_name=first_name,
                last_name=last_name,
                orcid=orcid or None,
                is_active=not options["inactive"],
            )
            self.stdout.write(
                self.style.SUCCESS(
                    "Created account pk=%s (%s)." % (account.pk, account.email)
                )
            )

        if orcid and not account.orcid:
            account.orcid = orcid

        # --- assign the author role for the article's journal ----------
        if journal and not options["no_role"]:
            role, role_created = core_models.Role.objects.get_or_create(
                slug="author", defaults={"name": "Author"}
            )
            core_models.AccountRole.objects.get_or_create(
                user=account, role=role, journal=journal
            )
            if role_created:
                self.stdout.write("Created missing 'author' Role.")

        # --- link frozen author -> account -----------------------------
        frozen_author.author = account
        frozen_author.frozen_email = ""  # linked account, don't store this value
        if not options["dry_run"]:
            frozen_author.save()
            account.save()

        self.stdout.write(
            self.style.SUCCESS(
                "Linked frozen author pk=%s to account pk=%s (%s)."
                % (
                    frozen_author.pk,
                    account.pk,
                    account.email,
                )
            )
        )
