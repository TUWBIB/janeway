"""
Serializers for the writable TUW API.

Input payloads are designed to be as close as possible to the JSON
produced by the readable API serializers in ``api.serializers``
(``IssueSerializer`` and ``ArticleSerializer``).

Write-time resolution rules (all scoped to the journal bound to the
request):
- ``issue_type``: a code string (e.g. "issue", "collection"), as
  produced by the readable API.
- ``license``: a ``short_name`` string (e.g. "CC-BY"), as shown by the
  readable API via ``LicenceSerializer``.
- ``section``: the section name (as shown by the readable API).
- ``authors``: list of dicts with ``first_name``, ``middle_name``,
  ``last_name``, ``name_suffix``, ``institution``, ``department``,
  ``country`` (mirrors ``FrozenAuthorSerializer``).
- ``cover_image`` / ``large_image``: base64 data URI (write-only).
"""

from rest_framework import serializers

from core import models as core_models
from journal import models as journal_models
from submission import models as submission_models

from api.tuw import images as tuw_images


class IssueWriteSerializer(serializers.Serializer):
    """
    Input serializer for creating and updating issues via POST/PUT on
    /api/tuw/issues/. Field names mirror the readable IssueSerializer,
    plus the TUW-specific issue fields.
    """

    volume = serializers.IntegerField(
        required=False,
        default=1,
        min_value=0,
        help_text="Volume number.",
    )
    issue = serializers.CharField(
        required=False,
        default="1",
        help_text="Issue number within the volume (string, as in the readable API).",
    )
    issue_title = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        help_text="Issue title, as in the readable API.",
    )
    date = serializers.DateTimeField(
        required=True,
        help_text="Publication date, as in the readable API.",
    )
    issue_type = serializers.CharField(
        required=False,
        allow_null=True,
        help_text="Issue type code for this journal (e.g. 'issue', 'collection'). "
        "Mirrors the readable API, which exposes the code rather than the id.",
    )
    issue_description = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        help_text="Issue description, as in the readable API.",
    )
    short_description = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        help_text="Short description for non-serial collections.",
    )
    code = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        help_text="Optional verbose URL slug for the issue.",
    )
    order = serializers.IntegerField(
        required=False,
        default=0,
        min_value=0,
        help_text="Position of the issue relative to other issues.",
    )
    # TUW-specific fields
    tuw_year = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="Publication year as claimed in the issue (may differ from the issue date).",
    )
    tuw_issue_str = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        max_length=10,
        help_text="TUW issue string.",
    )
    tuw_vlid = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="TUW volume/issue identifier.",
    )
    doi = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        max_length=255,
        help_text="DOI to be registered for the issue (not a URL).",
    )
    isbn = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        max_length=28,
        help_text="ISBN, relevant for non-serial collections.",
    )
    # Base64 image uploads (write-only)
    cover_image = serializers.CharField(
        required=False,
        allow_null=True,
        help_text="Base64-encoded issue cover image, as a data URI "
        "(e.g. 'data:image/png;base64,...'). Pass null to remove.",
    )
    large_image = serializers.CharField(
        required=False,
        allow_null=True,
        help_text="Base64-encoded landscape hero image, as a data URI "
        "(e.g. 'data:image/jpeg;base64,...'). Pass null to remove.",
    )

    def validate_issue_type(self, value):
        request = self.context.get("request")
        if value is None:
            return None
        journal = getattr(request, "journal", None)
        if journal is None:
            raise serializers.ValidationError("No journal bound to this request.")
        issue_type = (
            journal_models.IssueType.objects.filter(journal=journal, code=value).first()
        )
        if issue_type is None:
            available = list(
                journal_models.IssueType.objects.filter(journal=journal).values_list(
                    "code", flat=True
                )
            )
            raise serializers.ValidationError(
                "Unknown issue type code '{}'. Available codes for this journal: {}.".format(
                    value, ", ".join(available) if available else "none"
                )
            )
        return issue_type

    def create(self, validated_data):
        request = self.context["request"]
        journal = request.journal

        images = {
            field: validated_data.pop(field)
            for field in ("cover_image", "large_image")
            if validated_data.get(field) is not None
        }

        issue = journal_models.Issue.objects.create(
            journal=journal,
            issue_type=validated_data.pop("issue_type", None),
            date=validated_data.pop("date"),
            **validated_data,
        )

        for field_name, payload in images.items():
            try:
                tuw_images.assign_base64_image(issue, field_name, payload)
            except serializers.ValidationError as exc:
                issue.delete()
                raise

        return issue

    def update(self, instance, validated_data):
        # Enforced in the view: instance is already journal-scoped.
        images = {
            field: validated_data.pop(field)
            for field in ("cover_image", "large_image")
            if field in validated_data
        }

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        for field_name, payload in images.items():
            if payload is None:
                # Explicit removal of the image
                field = instance._meta.get_field(field_name)
                existing = getattr(instance, field_name, None)
                if existing:
                    field.storage.delete(existing.name)
                    setattr(instance, field_name, None)
                    instance.save(update_fields=[field_name])
            else:
                tuw_images.assign_base64_image(instance, field_name, payload)

        return instance


class SubmissionWriteSerializer(serializers.Serializer):
    """
    Input serializer for creating and updating submissions (articles)
    via POST/PUT on /api/tuw/submissions/. Field names mirror the
    readable ArticleSerializer.
    """

    title = serializers.CharField(
        required=True,
        allow_blank=True,
        max_length=999,
        help_text="Article title, as in the readable API.",
    )
    subtitle = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=999,
        help_text="Article subtitle (deprecated in the readable API, but still stored).",
    )
    abstract = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="Article abstract, as in the readable API.",
    )
    language = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=200,
        help_text="Primary language of the article, e.g. 'eng'.",
    )
    license = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=15,
        help_text="Licence short_name for this journal (e.g. 'CC-BY').",
    )
    keywords = serializers.ListField(
        child=serializers.CharField(max_length=200),
        required=False,
        allow_empty=True,
        help_text="List of keyword strings, as in the readable API.",
    )
    section = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=200,
        help_text="Section name for this journal, as in the readable API.",
    )
    authors = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        allow_empty=True,
        help_text="Ordered list of author dicts with first_name, middle_name, "
        "last_name, name_suffix, institution, department, country.",
    )
    date_submitted = serializers.DateTimeField(
        required=False,
        allow_null=True,
        help_text="Date the submission was made.",
    )
    date_accepted = serializers.DateTimeField(
        required=False,
        allow_null=True,
        help_text="Date the submission was accepted.",
    )

    def validate_license(self, value):
        request = self.context.get("request")
        if value in (None, ""):
            return None
        journal = getattr(request, "journal", None)
        if journal is None:
            raise serializers.ValidationError("No journal bound to this request.")
        licence = (
            submission_models.Licence.objects.filter(
                journal=journal,
                short_name=value,
            )
            .first()
            or submission_models.Licence.objects.filter(
                press=journal.press,
                short_name=value,
            ).first()
        )
        if licence is None:
            available = list(
                submission_models.Licence.objects.filter(journal=journal)
                .values_list("short_name", flat=True)
            )
            raise serializers.ValidationError(
                "Unknown licence '{}' for this journal. Available short names: {}.".format(
                    value, ", ".join(available) if available else "none"
                )
            )
        return licence

    def validate_section(self, value):
        request = self.context.get("request")
        if value in (None, ""):
            return None
        journal = getattr(request, "journal", None)
        if journal is None:
            raise serializers.ValidationError("No journal bound to this request.")
        section = (
            submission_models.Section.objects.filter(journal=journal, name=value).first()
        )
        if section is None:
            available = list(
                submission_models.Section.objects.filter(journal=journal).values_list(
                    "name", flat=True
                )
            )
            raise serializers.ValidationError(
                "Unknown section '{}' for this journal. Available sections: {}.".format(
                    value, ", ".join(str(s) for s in available) if available else "none"
                )
            )
        return section

    def validate(self, attrs):
        if attrs.get("authors"):
            for index, author in enumerate(attrs["authors"]):
                for key in ("first_name", "last_name"):
                    if not (author.get(key) or "").strip():
                        # Corporate authors may only have an institution
                        if not (author.get("institution") or "").strip():
                            raise serializers.ValidationError(
                                {
                                    "authors": "Author {} is missing a name "
                                    "(first_name/last_name or institution).".format(
                                        index + 1
                                    )
                                }
                            )
        return attrs

    def _apply_authors(self, article, authors):
        """
        Replace the article's FrozenAuthor records with the given list,
        setting order from list position and affiliations via the
        model's controlled-affiliation API.
        """
        article.frozenauthor_set.all().delete()
        for index, author in enumerate(authors, start=1):
            frozen_author = submission_models.FrozenAuthor.objects.create(
                article=article,
                first_name=(author.get("first_name") or "").strip(),
                middle_name=(author.get("middle_name") or "").strip(),
                last_name=(author.get("last_name") or "").strip(),
                name_prefix=(author.get("name_prefix") or author.get("salutation") or "").strip(),
                name_suffix=(author.get("name_suffix") or "").strip(),
                frozen_email=(author.get("email") or "").strip(),
                frozen_orcid=(author.get("orcid") or "").strip(),
                order=index,
            )
            institution = (author.get("institution") or "").strip()
            department = (author.get("department") or "").strip()
            country = (author.get("country") or "").strip()
            if institution or department or country:
                try:
                    core_models.ControlledAffiliation.get_or_create_without_ror(
                        institution=institution,
                        department=department,
                        country=country,
                        frozen_author=frozen_author,
                    )
                except Exception as exc:
                    raise serializers.ValidationError(
                        {
                            "authors": "Could not create affiliation for author {}: {}".format(
                                index, exc
                            )
                        }
                    )

    def _apply_keywords(self, article, keywords):
        """
        Replace the article's keyword set with the given list of words,
        reusing existing Keyword rows.
        """
        article.keywords.clear()
        for word in keywords:
            word = word.strip()
            if not word:
                continue
            keyword, _ = submission_models.Keyword.objects.get_or_create(word=word)
            article.keywords.add(keyword)

    def create(self, validated_data):
        request = self.context["request"]
        journal = request.journal

        authors = validated_data.pop("authors", [])
        keywords = validated_data.pop("keywords", [])

        article = submission_models.Article.objects.create(
            journal=journal,
            stage=submission_models.STAGE_UNASSIGNED,
            **validated_data,
        )
        try:
            self._apply_authors(article, authors)
            self._apply_keywords(article, keywords)
        except serializers.ValidationError:
            article.delete()
            raise
        return article

    def update(self, instance, validated_data):
        authors = validated_data.pop("authors", None)
        keywords = validated_data.pop("keywords", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if authors is not None:
            self._apply_authors(instance, authors)
        if keywords is not None:
            self._apply_keywords(instance, keywords)

        return instance
