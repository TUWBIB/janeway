import logging

from rest_framework import serializers

from core import models as core_models
from journal import models as journal_models
from submission import models as submission_models
from repository import models as repository_models

logger = logging.getLogger(__name__)


class LicenceSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = submission_models.Licence
        fields = ("name", "short_name", "text", "url")


class KeywordsSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = submission_models.Keyword
        fields = ("word",)

class FrozenAuthorSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = submission_models.FrozenAuthor
        fields = (
            "first_name",
            "middle_name",
            "last_name",
            "name_suffix",
            "institution",
            "department",
            "country",
        )

    country = serializers.ReadOnlyField(
        read_only=True,
        source="country.name",
    )


class GalleySerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = core_models.Galley
        fields = ("label", "type", "path")


class ArticleSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = submission_models.Article
        fields = (
            "pk",
            "title",
            "subtitle",
            "abstract",
            "language",
            "license",
            "keywords",
            "section",
            "is_remote",
            "remote_url",
            "frozenauthors",
            "date_submitted",
            "date_accepted",
            "date_published",
            "render_galley",
            "galleys",
        )

    license = LicenceSerializer()
    keywords = KeywordsSerializer(
        many=True,
        read_only=True,
    )
    section = serializers.ReadOnlyField(read_only=True, source="section.name")
    frozenauthors = FrozenAuthorSerializer(
        many=True,
        source="frozenauthor_set",
    )
    render_galley = GalleySerializer(
        read_only=True,
    )
    galleys = GalleySerializer(source="galley_set", many=True)


class PreprintSubjectSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = repository_models.Subject
        fields = ("name",)


class PreprintFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = repository_models.PreprintFile
        fields = (
            "original_filename",
            "mime_type",
            "download_url",
        )


class PreprintSupplementaryFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = repository_models.PreprintSupplementaryFile
        fields = (
            "url",
            "label",
        )


class IssueSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = journal_models.Issue
        fields = (
            "pk",
            "volume",
            "issue",
            "issue_title",
            "date",
            "issue_type",
            "issue_description",
            "cover_image",
            "large_image",
            "articles",
        )

    issue_type = serializers.ReadOnlyField(
        read_only=True,
        source="issue_type.code",
    )


# TUW
# bf - fix api using the requests host, which doesn't work at all in domain mode
class JournalSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = journal_models.Journal
        fields = (
            "pk",
            "code",
            "name",
            "publisher",
            "issn",
            "description",
            "current_issue",
            "default_cover_image",
            "default_large_image",
            "issues",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Store the request from context to build per-journal URLs
        self._request = self.context.get("request") if self.context else None

    def _build_api_url_with_journal_domain(self, journal, api_path):
        """Build an API URL with the journal's own domain as netloc.
        
        e.g., https://test.journal.ifm.tuwien.ac.at/api/issues/80/
        """
        from utils import logic
        # Use the journal's scheme but replace the netloc with the journal's domain
        return logic.build_url(
            netloc=journal.domain,
            scheme=self._request.scheme if self._request else "http",
            path=api_path,
        )

    issues = serializers.SerializerMethodField()

    def get_issues(self, obj):
        """Return list of issue detail URLs using each issue's journal domain."""
        request = self.context.get("request") if self.context else None
        if not request:
            return []
        issues = obj.issue_set.all()
        api_base = "/api/issues/"
        return [
            self._build_api_url_with_journal_domain(issue.journal, api_base + str(issue.pk) + "/")
            for issue in issues
        ]

    current_issue = serializers.SerializerMethodField()

    def get_current_issue(self, obj):
        """Return the current issue URL using the journal's own domain."""
        request = self.context.get("request") if self.context else None
        if not request:
            return None
        current_issue = obj.current_issue
        if not current_issue:
            return None
        return self._build_api_url_with_journal_domain(
            obj, "/api/issues/" + str(current_issue.pk) + "/"
        )


class RoleSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = core_models.Role
        fields = (
            "pk",
            "slug",
        )


class AccountSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = core_models.Account
        fields = (
            "pk",
            "email",
            "first_name",
            "middle_name",
            "last_name",
            "salutation",
            "orcid",
            "is_active",
        )


class PreprintAccountSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = core_models.Account
        fields = (
            "pk",
            "first_name",
            "middle_name",
            "last_name",
            "salutation",
            "orcid",
        )


class AccountRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = core_models.AccountRole
        fields = ("pk", "journal", "user", "role")

    def validate(self, data):
        request = self.context.get("request", None)
        role = data.get("role")

        excluded_roles = ["reader"]

        # if the current user is not staff add the journal-manager role to
        # the list of excluded roles.
        if not request or not request.user.is_staff:
            excluded_roles.append("journal-manager")

        if role.slug in excluded_roles:
            raise serializers.ValidationError(
                {"error": "You cannot add a user to that role via the API."}
            )

        return data


class RepositoryFieldAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = repository_models.RepositoryFieldAnswer
        fields = ["pk", "answer"]


class PreprintSerializer(serializers.ModelSerializer):
    class Meta:
        model = repository_models.Preprint
        fields = (
            "pk",
            "title",
            "abstract",
            "license",
            "keywords",
            "date_submitted",
            "date_accepted",
            "date_published",
            "doi",
            "preprint_doi",
            "authors",
            "subject",
            "files",
            "supplementary_files",
        )
        depth = 2

    authors = PreprintAccountSerializer(
        many=True,
        read_only=True,
    )
    license = LicenceSerializer()
    keywords = KeywordsSerializer(
        many=True,
        read_only=True,
    )
    subject = PreprintSubjectSerializer(
        many=True,
        read_only=True,
    )
    files = PreprintFileSerializer(
        source="preprintfile_set",
        many=True,
        read_only=True,
    )
    supplementary_files = PreprintSupplementaryFileSerializer(
        source="preprintsupplementaryfile_set",
        many=True,
        read_only=True,
    )
