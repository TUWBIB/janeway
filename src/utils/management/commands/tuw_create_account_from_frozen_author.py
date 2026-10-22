"""Creates a core.Account for a detached FrozenAuthor and links them.

Usage:
    manage.py tuw_create_account_from_frozen_author [frozen_email] [options]

Examples:
    manage.py tuw_create_account_from_frozen_author "jane.doe@example.com"
    manage.py tuw_create_account_from_frozen_author --pk 1210

Notes:
- The FrozenAuthor is identified by its ``frozen_email`` (case-insensitive)
  or by its pk via ``--pk``. If no detached record carries that email, a
  record whose ORCID matches an account's email is also tried via
  ``--orcid``.
- The account's email is taken from the frozen author's real email. If
  the author has none (e.g. a GND-only record), the placeholder scheme
  ``firstname.lastname@no.valid.email.com`` is used (matching the
  scheme flagged by ``Account.hasValidEmail``).
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
            nargs="?",
            default=None,
            help="Email stored on the detached FrozenAuthor (frozen_email).",
        )
        parser.add_argument(
            "--pk",
            type=int,
            default=None,
            help="FrozenAuthor pk to use instead of looking up by email.",
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
        frozen_email = (options["frozen_email"] or "").strip()
        pk = options["pk"]
        if not frozen_email and not pk:
            raise CommandError(
                "Provide a frozen_email or --pk to identify the FrozenAuthor."
            )

        # --- find the frozen author ------------------------------------
        fqs = submission_models.FrozenAuthor.objects.none()
        already_linked = None
        if pk is not None:
            frozen_author = (
                submission_models.FrozenAuthor.objects.filter(pk=pk).first()
            )
            if not frozen_author:
                raise CommandError("No FrozenAuthor found with pk %d." % pk)
            if frozen_author.author:
                self.stdout.write(
                    self.style.WARNING(
                        "FrozenAuthor pk=%s (%s) is already linked to account %r; "
                        "nothing to do."
                        % (
                            frozen_author.pk,
                            frozen_author.full_name(),
                            frozen_author.author.email,
                        )
                    )
                )
                return
            self.stdout.write(
                "Using FrozenAuthor pk=%s (%s) from --pk."
                % (frozen_author.pk, frozen_author.full_name())
            )
        else:
            fqs = submission_models.FrozenAuthor.objects.filter(
                frozen_email__iexact=frozen_email
            )
            if not fqs.exists():
                # A previous run already linked this record: linking clears
                # frozen_email (see associate_with_account()), so the record
                # is now only findable via its account's email.
                already_linked = (
                    submission_models.FrozenAuthor.objects.filter(
                        author__email__iexact=frozen_email
                    )
                    .order_by("pk")
                    .first()
                )
                if not already_linked:
                    orcid = options["orcid"]
                    if orcid:
                        fqs = submission_models.FrozenAuthor.objects.filter(
                            frozen_orcid=orcid
                        )
            if not fqs.exists():
                if already_linked:
                    self.stdout.write(
                        self.style.WARNING(
                            "FrozenAuthor pk=%s (%s) is already linked to "
                            "account %r (pk=%s); nothing to do."
                            % (
                                already_linked.pk,
                                already_linked.full_name(),
                                already_linked.author.email,
                                already_linked.author.pk,
                            )
                        )
                    )
                    return
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
                self.stdout.write(
                    self.style.WARNING(
                        "FrozenAuthor %s (%s) is already linked to account %r; "
                        "nothing to do."
                        % (
                            frozen_author.pk,
                            frozen_author.full_name(),
                            frozen_author.author.email,
                        )
                    )
                )
                return
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

        # The account email: prefer the frozen author's real email, fall
        # back to the placeholder scheme firstname.lastname@no.valid.email.com
        # (flagged by Account.hasValidEmail) when the author has none.
        account_email = frozen_author.account_email()
        if not frozen_author.real_email:
            self.stdout.write(
                self.style.WARNING(
                    "Author has no email address; using placeholder %s."
                    % account_email
                )
            )

        self.stdout.write(
            "Frozen author pk=%s %s | email=%s | orcid=%s | journal=%s"
            % (
                frozen_author.pk,
                frozen_author.full_name(),
                account_email,
                orcid or "-",
                journal.code if journal else "-",
            )
        )

        # --- find or create the account --------------------------------
        account = core_models.Account.objects.filter(
            email__iexact=account_email
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
                last_name = last_name or account_email.split("@")[0]

            if options["dry_run"]:
                self.stdout.write(
                    self.style.MIGRATE_HEADING(
                        "[dry-run] Would create account %s %s <%s> "
                        "(active=%s)."
                    )
                )
                return

            account = core_models.Account.objects.create(
                email=account_email,
                username=account_email.lower(),
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
