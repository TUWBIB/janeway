import base64
import io

from django.conf import settings
from django.test import TestCase, override_settings

from PIL import Image

from rest_framework.test import APIClient

from journal import models as journal_models
from submission import models as submission_models
from utils import logic
from utils.testing import helpers


def make_png_data_uri(width=8, height=8, color=(255, 0, 0)):
    """Create a tiny valid PNG and return it as a base64 data URI."""
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return "data:image/png;base64," + encoded


class TestTUWAPI(TestCase):
    """
    Tests for the writable TUW API under /api/tuw/.
    """

    @classmethod
    def setUpTestData(cls):
        cls.press = helpers.create_press()
        cls.journal, cls.journal_two = helpers.create_journals()
        cls.issue_type = journal_models.IssueType.objects.get(
            journal=cls.journal, code="issue"
        )
        cls.section = helpers.create_section(cls.journal, name="Article")
        cls.licence = helpers.create_licence(
            cls.journal, name="CC BY", short_name="CC-BY"
        )
        cls.api_client = APIClient()

    @property
    def auth_header(self):
        return {"HTTP_AUTHORIZATION": "Bearer " + settings.TUW_API_KEY}

    def journal_headers(self, journal=None):
        headers = dict(self.auth_header)
        headers["SERVER_NAME"] = (journal or self.journal).domain
        return headers

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    @override_settings(URL_CONFIG="domain")
    def test_request_without_api_key_is_rejected(self):
        response = self.api_client.post(
            "/api/tuw/issues/",
            data={"date": logic.get_aware_datetime("2024-01-01").isoformat()},
            format="json",
            SERVER_NAME=self.journal.domain,
        )
        self.assertEqual(response.status_code, 401)

    @override_settings(URL_CONFIG="domain")
    def test_request_with_invalid_api_key_is_rejected(self):
        response = self.api_client.post(
            "/api/tuw/issues/",
            data={"date": logic.get_aware_datetime("2024-01-01").isoformat()},
            format="json",
            SERVER_NAME=self.journal.domain,
            HTTP_AUTHORIZATION="Bearer not-the-right-key",
        )
        self.assertEqual(response.status_code, 401)

    @override_settings(URL_CONFIG="domain")
    def test_request_on_press_domain_is_rejected(self):
        response = self.api_client.post(
            "/api/tuw/issues/",
            data={"date": logic.get_aware_datetime("2024-01-01").isoformat()},
            format="json",
            SERVER_NAME=self.press.domain,
            HTTP_AUTHORIZATION="Bearer " + settings.TUW_API_KEY,
        )
        self.assertEqual(response.status_code, 404)

    # ------------------------------------------------------------------
    # Issues: create
    # ------------------------------------------------------------------

    @override_settings(URL_CONFIG="domain")
    def test_issue_can_be_created(self):
        response = self.api_client.post(
            "/api/tuw/issues/",
            data={
                "volume": 7,
                "issue": "2",
                "issue_title": "A spring special",
                "date": logic.get_aware_datetime("2024-03-01").isoformat(),
                "issue_type": "issue",
                "issue_description": "Special issue description",
                "tuw_year": 2024,
                "tuw_vlid": 42,
                "doi": "10.1234/spring.2024.2",
            },
            format="json",
            SERVER_NAME=self.journal.domain,
            HTTP_AUTHORIZATION="Bearer " + settings.TUW_API_KEY,
        )
        self.assertEqual(response.status_code, 201, response.content)
        issue = journal_models.Issue.objects.get(pk=response.data["pk"])
        self.assertEqual(issue.journal, self.journal)
        self.assertEqual(issue.volume, 7)
        self.assertEqual(issue.issue, "2")
        self.assertEqual(issue.issue_title, "A spring special")
        self.assertEqual(issue.issue_type, self.issue_type)
        self.assertEqual(issue.issue_description, "Special issue description")
        self.assertEqual(issue.tuw_year, 2024)
        self.assertEqual(issue.tuw_vlid, 42)
        self.assertEqual(issue.doi, "10.1234/spring.2024.2")
        # The response mirrors the readable IssueSerializer
        self.assertEqual(response.data["issue_type"], "issue")
        self.assertIn("articles", response.data)

    @override_settings(URL_CONFIG="domain")
    def test_issue_create_requires_date(self):
        response = self.api_client.post(
            "/api/tuw/issues/",
            data={"volume": 1, "issue": "1"},
            format="json",
            SERVER_NAME=self.journal.domain,
            HTTP_AUTHORIZATION="Bearer " + settings.TUW_API_KEY,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("date", response.data)

    @override_settings(URL_CONFIG="domain")
    def test_issue_create_rejects_unknown_issue_type(self):
        response = self.api_client.post(
            "/api/tuw/issues/",
            data={
                "date": logic.get_aware_datetime("2024-03-01").isoformat(),
                "issue_type": "not-a-real-type",
            },
            format="json",
            SERVER_NAME=self.journal.domain,
            HTTP_AUTHORIZATION="Bearer " + settings.TUW_API_KEY,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("issue_type", response.data)

    @override_settings(URL_CONFIG="domain")
    def test_issue_create_with_base64_images(self):
        response = self.api_client.post(
            "/api/tuw/issues/",
            data={
                "date": logic.get_aware_datetime("2024-03-01").isoformat(),
                "issue_type": "issue",
                "cover_image": make_png_data_uri(),
                "large_image": make_png_data_uri(color=(0, 255, 0)),
            },
            format="json",
            SERVER_NAME=self.journal.domain,
            HTTP_AUTHORIZATION="Bearer " + settings.TUW_API_KEY,
        )
        self.assertEqual(response.status_code, 201, response.content)
        issue = journal_models.Issue.objects.get(pk=response.data["pk"])
        self.assertTrue(issue.cover_image)
        self.assertTrue(issue.large_image)
        self.assertTrue(issue.cover_image.name.endswith(".png"))
        # readable API exposes the URL
        self.assertTrue(response.data["cover_image"].endswith(".png"))

    @override_settings(URL_CONFIG="domain")
    def test_issue_create_rejects_invalid_image_data(self):
        response = self.api_client.post(
            "/api/tuw/issues/",
            data={
                "date": logic.get_aware_datetime("2024-03-01").isoformat(),
                "cover_image": "data:image/png;base64,!!!not-base64!!!",
            },
            format="json",
            SERVER_NAME=self.journal.domain,
            HTTP_AUTHORIZATION="Bearer " + settings.TUW_API_KEY,
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(journal_models.Issue.objects.exists())

    @override_settings(URL_CONFIG="domain")
    def test_issue_create_rejects_non_image_bytes(self):
        encoded = base64.b64encode(b"this is not an image at all").decode("ascii")
        response = self.api_client.post(
            "/api/tuw/issues/",
            data={
                "date": logic.get_aware_datetime("2024-03-01").isoformat(),
                "cover_image": "data:image/png;base64," + encoded,
            },
            format="json",
            SERVER_NAME=self.journal.domain,
            HTTP_AUTHORIZATION="Bearer " + settings.TUW_API_KEY,
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(journal_models.Issue.objects.exists())

    # ------------------------------------------------------------------
    # Issues: update
    # ------------------------------------------------------------------

    def _create_issue(self, **kwargs):
        defaults = {
            "journal": self.journal,
            "volume": 1,
            "issue": "1",
            "issue_title": "Original title",
            "issue_type": self.issue_type,
            "date": logic.get_aware_datetime("2024-01-01"),
        }
        defaults.update(kwargs)
        return journal_models.Issue.objects.create(**defaults)

    @override_settings(URL_CONFIG="domain")
    def test_issue_can_be_updated(self):
        issue = self._create_issue()
        response = self.api_client.put(
            "/api/tuw/issues/{0}/".format(issue.pk),
            data={
                "volume": 9,
                "issue": "4",
                "issue_title": "Updated title",
                "date": logic.get_aware_datetime("2024-06-01").isoformat(),
                "issue_type": "issue",
            },
            format="json",
            SERVER_NAME=self.journal.domain,
            HTTP_AUTHORIZATION="Bearer " + settings.TUW_API_KEY,
        )
        self.assertEqual(response.status_code, 200, response.content)
        issue.refresh_from_db()
        self.assertEqual(issue.volume, 9)
        self.assertEqual(issue.issue, "4")
        self.assertEqual(issue.issue_title, "Updated title")

    @override_settings(URL_CONFIG="domain")
    def test_issue_update_can_add_and_remove_images(self):
        issue = self._create_issue()
        response = self.api_client.put(
            "/api/tuw/issues/{0}/".format(issue.pk),
            data={
                "volume": 1,
                "issue": "1",
                "date": logic.get_aware_datetime("2024-01-01").isoformat(),
                "cover_image": make_png_data_uri(),
            },
            format="json",
            SERVER_NAME=self.journal.domain,
            HTTP_AUTHORIZATION="Bearer " + settings.TUW_API_KEY,
        )
        self.assertEqual(response.status_code, 200, response.content)
        issue.refresh_from_db()
        self.assertTrue(issue.cover_image)
        first_path = issue.cover_image.path

        # replace, then explicitly remove
        response = self.api_client.put(
            "/api/tuw/issues/{0}/".format(issue.pk),
            data={
                "volume": 1,
                "issue": "1",
                "date": logic.get_aware_datetime("2024-01-01").isoformat(),
                "cover_image": make_png_data_uri(color=(0, 0, 255)),
            },
            format="json",
            SERVER_NAME=self.journal.domain,
            HTTP_AUTHORIZATION="Bearer " + settings.TUW_API_KEY,
        )
        self.assertEqual(response.status_code, 200, response.content)
        issue.refresh_from_db()
        self.assertTrue(issue.cover_image)
        self.assertNotEqual(issue.cover_image.path, first_path)

        response = self.api_client.put(
            "/api/tuw/issues/{0}/".format(issue.pk),
            data={
                "volume": 1,
                "issue": "1",
                "date": logic.get_aware_datetime("2024-01-01").isoformat(),
                "cover_image": None,
            },
            format="json",
            SERVER_NAME=self.journal.domain,
            HTTP_AUTHORIZATION="Bearer " + settings.TUW_API_KEY,
        )
        self.assertEqual(response.status_code, 200, response.content)
        issue.refresh_from_db()
        self.assertFalse(issue.cover_image)

    @override_settings(URL_CONFIG="domain")
    def test_issue_update_cannot_touch_other_journals_issues(self):
        other_issue = self._create_issue(journal=self.journal_two)
        response = self.api_client.put(
            "/api/tuw/issues/{0}/".format(other_issue.pk),
            data={
                "volume": 2,
                "issue": "2",
                "date": logic.get_aware_datetime("2024-02-01").isoformat(),
            },
            format="json",
            SERVER_NAME=self.journal.domain,
            HTTP_AUTHORIZATION="Bearer " + settings.TUW_API_KEY,
        )
        self.assertEqual(response.status_code, 404)
        other_issue.refresh_from_db()
        self.assertEqual(other_issue.volume, 1)

    @override_settings(URL_CONFIG="domain")
    def test_issue_update_of_missing_issue_returns_404(self):
        response = self.api_client.put(
            "/api/tuw/issues/99999/",
            data={
                "volume": 1,
                "issue": "1",
                "date": logic.get_aware_datetime("2024-01-01").isoformat(),
            },
            format="json",
            SERVER_NAME=self.journal.domain,
            HTTP_AUTHORIZATION="Bearer " + settings.TUW_API_KEY,
        )
        self.assertEqual(response.status_code, 404)

    # ------------------------------------------------------------------
    # Submissions: create
    # ------------------------------------------------------------------

    @override_settings(URL_CONFIG="domain")
    def test_submission_can_be_created(self):
        response = self.api_client.post(
            "/api/tuw/submissions/",
            data={
                "title": {
                    "raw": "A brand new article",
                    "de": "Ein brandneuer Artikel",
                },
                "abstract": {
                    "raw": "The abstract of the article.",
                    "de": "Die Zusammenfassung des Artikels.",
                },
                "language": "eng",
                "license": "CC-BY",
                "keywords": {
                    "en": ["open access", "testing"],
                    "de": ["Offener Zugang", "Test"],
                },
                "section": "Article",
                "authors": [
                    {
                        "first_name": "Erika",
                        "last_name": "Mustermann",
                        "institution": "TU Wien",
                        "country": "AT",
                    },
                    {
                        "first_name": "John",
                        "last_name": "Doe",
                        "institution": "Some University",
                    },
                ],
                "date_submitted": logic.get_aware_datetime("2024-04-01").isoformat(),
            },
            format="json",
            SERVER_NAME=self.journal.domain,
            HTTP_AUTHORIZATION="Bearer " + settings.TUW_API_KEY,
        )
        self.assertEqual(response.status_code, 201, response.content)
        article = submission_models.Article.objects.get(pk=response.data["pk"])
        self.assertEqual(article.journal, self.journal)
        self.assertEqual(article.title_en, "A brand new article")
        self.assertEqual(article.title_de, "Ein brandneuer Artikel")
        self.assertEqual(article.abstract_en, "The abstract of the article.")
        self.assertEqual(article.abstract_de, "Die Zusammenfassung des Artikels.")
        self.assertEqual(article.language, "eng")
        self.assertEqual(article.license, self.licence)
        self.assertEqual(article.section, self.section)
        self.assertEqual(
            list(
                article.keywords.filter(language="en").values_list(
                    "word", flat=True
                )
            ),
            ["open access", "testing"],
        )
        self.assertEqual(
            list(
                article.keywords.filter(language="de").values_list(
                    "word", flat=True
                )
            ),
            ["Offener Zugang", "Test"],
        )
        self.assertEqual(article.stage, submission_models.STAGE_UNASSIGNED)
        authors = list(article.frozenauthor_set.order_by("order"))
        self.assertEqual(len(authors), 2)
        self.assertEqual(authors[0].first_name, "Erika")
        self.assertEqual(authors[0].last_name, "Mustermann")
        self.assertEqual(authors[0].order, 1)
        self.assertEqual(authors[0].institution, "TU Wien")
        self.assertEqual(authors[1].first_name, "John")
        self.assertEqual(authors[1].order, 2)
        # the readable API shape for the response
        self.assertEqual(response.data["frozenauthors"][0]["first_name"], "Erika")
        self.assertEqual(response.data["section"], "Article")
        self.assertEqual(response.data["keywords"], ["open access", "testing"])
        self.assertEqual(response.data["keywords_de"], ["Offener Zugang", "Test"])
        self.assertEqual(
            response.data["translations"],
            {
                "title": {
                    "en": "A brand new article",
                    "de": "Ein brandneuer Artikel",
                },
                "subtitle": {"en": None, "de": None},
                "abstract": {
                    "en": "The abstract of the article.",
                    "de": "Die Zusammenfassung des Artikels.",
                },
            },
        )

    @override_settings(URL_CONFIG="domain")
    def test_submission_create_requires_title(self):
        response = self.api_client.post(
            "/api/tuw/submissions/",
            data={"abstract": {"raw": "No title here"}},
            format="json",
            SERVER_NAME=self.journal.domain,
            HTTP_AUTHORIZATION="Bearer " + settings.TUW_API_KEY,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("title", response.data)

    @override_settings(URL_CONFIG="domain")
    def test_submission_create_rejects_empty_title(self):
        response = self.api_client.post(
            "/api/tuw/submissions/",
            data={"title": {"raw": "  ", "de": "   "}},
            format="json",
            SERVER_NAME=self.journal.domain,
            HTTP_AUTHORIZATION="Bearer " + settings.TUW_API_KEY,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("title", response.data)
        self.assertFalse(submission_models.Article.objects.exists())

    @override_settings(URL_CONFIG="domain")
    def test_submission_create_rejects_unknown_licence(self):
        response = self.api_client.post(
            "/api/tuw/submissions/",
            data={"title": "X", "license": "NOT-A-LICENCE"},
            format="json",
            SERVER_NAME=self.journal.domain,
            HTTP_AUTHORIZATION="Bearer " + settings.TUW_API_KEY,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("license", response.data)
        self.assertFalse(submission_models.Article.objects.exists())

    @override_settings(URL_CONFIG="domain")
    def test_submission_create_rejects_unknown_section(self):
        response = self.api_client.post(
            "/api/tuw/submissions/",
            data={"title": "X", "section": "No Such Section"},
            format="json",
            SERVER_NAME=self.journal.domain,
            HTTP_AUTHORIZATION="Bearer " + settings.TUW_API_KEY,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("section", response.data)

    @override_settings(URL_CONFIG="domain")
    def test_submission_create_rejects_author_without_name(self):
        response = self.api_client.post(
            "/api/tuw/submissions/",
            data={"title": {"raw": "X"}, "authors": [{"first_name": "No"}]},
            format="json",
            SERVER_NAME=self.journal.domain,
            HTTP_AUTHORIZATION="Bearer " + settings.TUW_API_KEY,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("authors", response.data)

    # ------------------------------------------------------------------
    # Submissions: update
    # ------------------------------------------------------------------

    def _create_submission(self, **kwargs):
        defaults = {
            "journal": self.journal,
            "title": "Original article",
            "section": self.section,
            "stage": submission_models.STAGE_UNASSIGNED,
        }
        defaults.update(kwargs)
        return submission_models.Article.objects.create(**defaults)

    @override_settings(URL_CONFIG="domain")
    def test_submission_can_be_updated(self):
        article = self._create_submission()
        response = self.api_client.put(
            "/api/tuw/submissions/{0}/".format(article.pk),
            data={
                "title": {"raw": "A revised title", "de": "Ein überarbeiteter Titel"},
                "abstract": {"raw": "A revised abstract."},
                "language": "deu",
                "keywords": {"en": ["only one"]},
                "authors": [
                    {
                        "first_name": "New",
                        "last_name": "Author",
                        "institution": "Other University",
                    }
                ],
            },
            format="json",
            SERVER_NAME=self.journal.domain,
            HTTP_AUTHORIZATION="Bearer " + settings.TUW_API_KEY,
        )
        self.assertEqual(response.status_code, 200, response.content)
        article.refresh_from_db()
        self.assertEqual(article.title_en, "A revised title")
        self.assertEqual(article.title_de, "Ein überarbeiteter Titel")
        self.assertEqual(article.abstract_en, "A revised abstract.")
        self.assertEqual(article.language, "deu")
        self.assertEqual(
            list(
                article.keywords.filter(language="en").values_list(
                    "word", flat=True
                )
            ),
            ["only one"],
        )
        self.assertEqual(
            list(
                article.keywords.filter(language="de").values_list(
                    "word", flat=True
                )
            ),
            [],
        )
        authors = list(article.frozenauthor_set.order_by("order"))
        self.assertEqual(len(authors), 1)
        self.assertEqual(authors[0].last_name, "Author")
        self.assertEqual(authors[0].institution, "Other University")

    @override_settings(URL_CONFIG="domain")
    def test_submission_update_cannot_touch_other_journals_articles(self):
        other_article = self._create_submission(journal=self.journal_two)
        response = self.api_client.put(
            "/api/tuw/submissions/{0}/".format(other_article.pk),
            data={"title": {"raw": "Hijacked!"}},
            format="json",
            SERVER_NAME=self.journal.domain,
            HTTP_AUTHORIZATION="Bearer " + settings.TUW_API_KEY,
        )
        self.assertEqual(response.status_code, 404)
        other_article.refresh_from_db()
        self.assertEqual(other_article.title, "Original article")

    @override_settings(URL_CONFIG="domain")
    def test_submission_update_of_missing_article_returns_404(self):
        response = self.api_client.put(
            "/api/tuw/submissions/99999/",
            data={"title": {"raw": "Ghost"}},
            format="json",
            SERVER_NAME=self.journal.domain,
            HTTP_AUTHORIZATION="Bearer " + settings.TUW_API_KEY,
        )
        self.assertEqual(response.status_code, 404)

    # ------------------------------------------------------------------
    # Submissions: multilingual fields
    # ------------------------------------------------------------------

    def _put_submission(self, article, data):
        return self.api_client.put(
            "/api/tuw/submissions/{0}/".format(article.pk),
            data=data,
            format="json",
            SERVER_NAME=self.journal.domain,
            HTTP_AUTHORIZATION="Bearer " + settings.TUW_API_KEY,
        )

    @override_settings(URL_CONFIG="domain")
    def test_submission_creates_german_only_fields_without_english_copies(self):
        # German-only title/abstract must not be duplicated into the
        # English translation columns by the save.
        response = self.api_client.post(
            "/api/tuw/submissions/",
            data={
                "title": {"de": "Nur auf Deutsch"},
                "abstract": {"de": "Nur Zusammenfassung"},
                "language": "deu",
            },
            format="json",
            SERVER_NAME=self.journal.domain,
            HTTP_AUTHORIZATION="Bearer " + settings.TUW_API_KEY,
        )
        self.assertEqual(response.status_code, 201, response.content)
        article = submission_models.Article.objects.get(pk=response.data["pk"])
        self.assertEqual(article.title_de, "Nur auf Deutsch")
        self.assertIn(article.title_en, ("", None))
        self.assertEqual(article.abstract_de, "Nur Zusammenfassung")
        self.assertIn(article.abstract_en, ("", None))

    @override_settings(URL_CONFIG="domain")
    def test_submission_explicit_en_overrides_raw(self):
        response = self.api_client.post(
            "/api/tuw/submissions/",
            data={
                "title": {"raw": "Primary title", "en": "English title"},
            },
            format="json",
            SERVER_NAME=self.journal.domain,
            HTTP_AUTHORIZATION="Bearer " + settings.TUW_API_KEY,
        )
        self.assertEqual(response.status_code, 201, response.content)
        article = submission_models.Article.objects.get(pk=response.data["pk"])
        self.assertEqual(article.title_en, "English title")
        # an explicit empty 'en' clears the English value
        response = self._put_submission(
            article, {"title": {"raw": "Primary title", "en": " "}}
        )
        self.assertEqual(response.status_code, 200, response.content)
        article.refresh_from_db()
        self.assertIn(article.title_en, ("", None))

    @override_settings(URL_CONFIG="domain")
    def test_submission_update_partial_translation_preserves_unmentioned(self):
        article = self._create_submission()
        article.title_en = "Old English"
        article.title_de = "Alter Deutsch"
        article.subtitle_de = "Alter Untertitel"
        article.save()

        # only the German title is provided; the rest must survive
        response = self._put_submission(article, {"title": {"de": "Neu Deutsch"}})
        self.assertEqual(response.status_code, 200, response.content)
        article.refresh_from_db()
        self.assertEqual(article.title_de, "Neu Deutsch")
        self.assertEqual(article.title_en, "Old English")
        self.assertEqual(article.subtitle_de, "Alter Untertitel")

        # clearing a translation with null/empty
        response = self._put_submission(article, {"title": {"de": None}})
        self.assertEqual(response.status_code, 200, response.content)
        article.refresh_from_db()
        self.assertIn(article.title_de, ("", None))
        self.assertEqual(article.title_en, "Old English")

    @override_settings(URL_CONFIG="domain")
    def test_submission_update_subtitle_roundtrip(self):
        article = self._create_submission()
        response = self._put_submission(
            article,
            {"subtitle": {"raw": "English sub", "de": "Deutscher Untertitel"}},
        )
        self.assertEqual(response.status_code, 200, response.content)
        article.refresh_from_db()
        self.assertEqual(article.subtitle_en, "English sub")
        self.assertEqual(article.subtitle_de, "Deutscher Untertitel")
        self.assertEqual(
            response.data["translations"]["subtitle"],
            {"en": "English sub", "de": "Deutscher Untertitel"},
        )

    @override_settings(URL_CONFIG="domain")
    def test_submission_keywords_language_sets_are_independent(self):
        article = self._create_submission()
        response = self._put_submission(
            article,
            {
                "keywords": {
                    "en": ["en one", "en two"],
                    "de": ["ein", "zwei"],
                }
            },
        )
        self.assertEqual(response.status_code, 200, response.content)
        article.refresh_from_db()
        self.assertEqual(
            list(
                article.keywords.filter(language="en").values_list(
                    "word", flat=True
                )
            ),
            ["en one", "en two"],
        )
        self.assertEqual(
            list(
                article.keywords.filter(language="de").values_list(
                    "word", flat=True
                )
            ),
            ["ein", "zwei"],
        )

        # order follows the payload and is preserved
        self.assertEqual(
            [
                row.keyword.word
                for row in submission_models.KeywordArticle.objects.filter(
                    article=article, keyword__language="en"
                ).order_by("order")
            ],
            ["en one", "en two"],
        )

        # an empty list clears only that language
        response = self._put_submission(article, {"keywords": {"de": []}})
        self.assertEqual(response.status_code, 200, response.content)
        article.refresh_from_db()
        self.assertEqual(
            list(
                article.keywords.filter(language="de").values_list(
                    "word", flat=True
                )
            ),
            [],
        )
        self.assertEqual(
            list(
                article.keywords.filter(language="en").values_list(
                    "word", flat=True
                )
            ),
            ["en one", "en two"],
        )

    @override_settings(URL_CONFIG="domain")
    def test_submission_keywords_same_word_in_both_languages(self):
        article = self._create_submission()
        response = self._put_submission(
            article,
            {"keywords": {"en": ["open access"], "de": ["open access"]}},
        )
        self.assertEqual(response.status_code, 200, response.content)
        article.refresh_from_db()
        self.assertEqual(
            list(
                article.keywords.filter(language="en").values_list(
                    "word", flat=True
                )
            ),
            ["open access"],
        )
        self.assertEqual(
            list(
                article.keywords.filter(language="de").values_list(
                    "word", flat=True
                )
            ),
            ["open access"],
        )
        self.assertEqual(
            submission_models.Keyword.objects.filter(word="open access").count(), 2
        )

    @override_settings(URL_CONFIG="domain")
    def test_submission_keywords_reject_unknown_language(self):
        response = self.api_client.post(
            "/api/tuw/submissions/",
            data={
                "title": {"raw": "X"},
                "keywords": {"fr": ["un mot"]},
            },
            format="json",
            SERVER_NAME=self.journal.domain,
            HTTP_AUTHORIZATION="Bearer " + settings.TUW_API_KEY,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("keywords", response.data)
        self.assertFalse(submission_models.Article.objects.exists())

    @override_settings(URL_CONFIG="domain")
    def test_submission_rejects_non_object_translatable_field(self):
        response = self.api_client.post(
            "/api/tuw/submissions/",
            data={"title": "just a string"},
            format="json",
            SERVER_NAME=self.journal.domain,
            HTTP_AUTHORIZATION="Bearer " + settings.TUW_API_KEY,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("title", response.data)
        self.assertFalse(submission_models.Article.objects.exists())
