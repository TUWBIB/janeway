"""
Writable API views for TUW integrations, reachable under /api/tuw/.

All endpoints are machine-to-machine, authenticated with a shared
``Authorization: Bearer <TUW_API_KEY>`` header (see
``api.tuw.permissions.IsTUWAPIKey``) and scoped to the journal resolved
from the request domain (``request.journal``).

Responses use the readable API serializers (``IssueSerializer`` and
``ArticleSerializer`` from ``api.serializers``) so that clients can
round-trip the JSON they fetch from the read endpoints.
"""

from django.shortcuts import get_object_or_404

from drf_spectacular.renderers import (
    OpenApiJsonRenderer,
    OpenApiJsonRenderer2,
    OpenApiYamlRenderer,
    OpenApiYamlRenderer2,
)
from drf_spectacular.utils import extend_schema, extend_schema_view
from drf_spectacular.views import SpectacularAPIView
from rest_framework import renderers, status
from rest_framework.exceptions import NotAuthenticated
from rest_framework.generics import (
    CreateAPIView,
    RetrieveUpdateAPIView,
)
from rest_framework.response import Response

from api import serializers as read_serializers
from journal import models as journal_models
from submission import models as submission_models
from utils.logger import get_logger

from api.tuw import serializers as tuw_serializers
from api.tuw.permissions import IsTUWAPIKey

logger = get_logger(__name__)


class TUWAuthMixin:
    """
    Authentication for the writable TUW API: a shared
    ``Authorization: Bearer <TUW_API_KEY>`` header (no per-user session).
    """

    permission_classes = [IsTUWAPIKey]
    authentication_classes = []

    def handle_exception(self, exc):
        if isinstance(exc, NotAuthenticated):
            # DRF maps NotAuthenticated to 403 by default, but this API
            # uses a bearer token, so 401 is the correct status.
            return Response(
                {"detail": "Invalid or missing API key."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        return super().handle_exception(exc)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context


class TUWCreateAPIView(TUWAuthMixin, CreateAPIView):
    """Base for the POST endpoints of the writable TUW API."""

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        logger.info(
            "TUW API: created %s %s for journal %s",
            self.serializer_class.__name__,
            instance.pk,
            request.journal.code,
        )
        response_serializer = self.get_response_serializer(instance)
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
        )


class TUWRetrieveUpdateAPIView(TUWAuthMixin, RetrieveUpdateAPIView):
    """
    Base for the PUT endpoints. Only objects belonging to the journal
    bound to the request are reachable; anything else (including
    objects of other journals) yields a 404.
    """

    def get_object(self):
        return get_object_or_404(
            self.get_journal_scoped_queryset(), pk=self.kwargs["pk"]
        )

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        logger.info(
            "TUW API: updated %s %s for journal %s",
            self.serializer_class.__name__,
            instance.pk,
            request.journal.code,
        )
        response_serializer = self.get_response_serializer(instance)
        return Response(response_serializer.data)

    def get_response_serializer(self, instance):
        raise NotImplementedError


@extend_schema_view(
    post=extend_schema(
        operation_id="tuw_issue_create",
        tags=["tuw-issues"],
        summary="Create an issue",
        description=(
            "Creates an issue for the journal bound to the request domain. "
            "The response is the readable API's issue representation, which "
            "can be sent back to the update endpoint."
        ),
        request={"application/json": tuw_serializers.IssueWriteSerializer},
        responses={
            201: read_serializers.IssueSerializer,
            400: tuw_serializers.TUW_VALIDATION_ERROR,
            401: tuw_serializers.TuwErrorSerializer,
        },
        auth=[{"TuwBearer": []}],
    ),
)
class TUWIssueCreateView(TUWCreateAPIView):
    """POST /api/tuw/issues/ — create an issue for the current journal."""

    serializer_class = tuw_serializers.IssueWriteSerializer

    def get_response_serializer(self, instance):
        return read_serializers.IssueSerializer(
            instance, context={"request": self.request}
        )


@extend_schema_view(
    put=extend_schema(
        operation_id="tuw_issue_update",
        tags=["tuw-issues"],
        summary="Update an issue",
        description=(
            "Updates an issue of the journal bound to the request domain. "
            "Issues of other journals are not reachable (404). Omitted "
            "fields are left unchanged, except the image fields where a "
            "value of null removes the image."
        ),
        request={"application/json": tuw_serializers.IssueWriteSerializer},
        responses={
            200: read_serializers.IssueSerializer,
            400: tuw_serializers.TUW_VALIDATION_ERROR,
            401: tuw_serializers.TuwErrorSerializer,
            404: tuw_serializers.TuwErrorSerializer,
        },
        auth=[{"TuwBearer": []}],
    ),
)
class TUWIssueUpdateView(TUWRetrieveUpdateAPIView):
    """PUT /api/tuw/issues/<pk>/ — update an issue of the current journal."""

    serializer_class = tuw_serializers.IssueWriteSerializer

    def get_journal_scoped_queryset(self):
        return journal_models.Issue.objects.filter(journal=self.request.journal)

    def get_response_serializer(self, instance):
        return read_serializers.IssueSerializer(
            instance, context={"request": self.request}
        )


@extend_schema_view(
    post=extend_schema(
        operation_id="tuw_submission_create",
        tags=["tuw-submissions"],
        summary="Create a submission",
        description=(
            "Creates a submission (article) for the journal bound to the "
            "request domain. A title (at least one of 'raw', 'en' or 'de') "
            "is required. The response is the readable API's article "
            "representation, which can be sent back to the update endpoint."
        ),
        request={"application/json": tuw_serializers.SubmissionWriteSerializer},
        responses={
            201: read_serializers.ArticleSerializer,
            400: tuw_serializers.TUW_VALIDATION_ERROR,
            401: tuw_serializers.TuwErrorSerializer,
        },
        auth=[{"TuwBearer": []}],
    ),
)
class TUWSubmissionCreateView(TUWCreateAPIView):
    """POST /api/tuw/submissions/ — create a submission for the current journal."""

    serializer_class = tuw_serializers.SubmissionWriteSerializer

    def get_response_serializer(self, instance):
        return read_serializers.ArticleSerializer(
            instance, context={"request": self.request}
        )


@extend_schema_view(
    put=extend_schema(
        operation_id="tuw_submission_update",
        tags=["tuw-submissions"],
        summary="Update a submission",
        description=(
            "Updates a submission (article) of the journal bound to the "
            "request domain. Submissions of other journals are not "
            "reachable (404). Omitted fields and translation keys are left "
            "unchanged; a value of null clears a translation."
        ),
        request={"application/json": tuw_serializers.SubmissionWriteSerializer},
        responses={
            200: read_serializers.ArticleSerializer,
            400: tuw_serializers.TUW_VALIDATION_ERROR,
            401: tuw_serializers.TuwErrorSerializer,
            404: tuw_serializers.TuwErrorSerializer,
        },
        auth=[{"TuwBearer": []}],
    ),
)
class TUWSubmissionUpdateView(TUWRetrieveUpdateAPIView):
    """PUT /api/tuw/submissions/<pk>/ — update a submission of the current journal."""

    serializer_class = tuw_serializers.SubmissionWriteSerializer

    def get_journal_scoped_queryset(self):
        return submission_models.Article.objects.filter(journal=self.request.journal)

    def get_response_serializer(self, instance):
        return read_serializers.ArticleSerializer(
            instance, context={"request": self.request}
        )


class TUWOpenApiHtmlRenderer(renderers.BaseRenderer):
    """
    Self-contained HTML landing page for the writable TUW API.

    Rendered when a browser (or a client without an explicit OpenAPI
    media type / ``?format`` override) requests the schema endpoint. The
    page shows the API title, a short description and links to the raw
    YAML (``?format=yaml``) and JSON (``?format=json``) documents. It has
    no external dependencies and works offline.
    """

    media_type = "text/html"
    format = "html"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        request = (renderer_context or {}).get("request")
        base = (
            request.build_absolute_uri(self._strip_query(request))
            if request
            else "/api/tuw/schema/"
        )

        info = (data or {}).get("info", {})
        title = info.get("title", "TUW Writable API")
        description = info.get("description", "")
        version = info.get("version", "")

        def safe(text):
            from html import escape
            return escape(str(text or ""), quote=True)

        yaml_url = base + "?format=yaml"
        json_url = base + "?format=json"

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{safe(title)}</title>
<style>
 body {{ font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
        margin: 2rem auto; max-width: 48rem; color: #222; line-height: 1.5; }}
 code {{ background: #f2f2f2; padding: .1rem .35rem; border-radius: 3px; }}
 a {{ color: #0366d6; }}
 .links {{ display: flex; gap: 1rem; }}
 .badge {{ font-size: .8rem; color: #555; }}
</style>
</head>
<body>
<h1>{safe(title)}</h1>
<p>{safe(description)}</p>
<p class="badge">Version: {safe(version)}</p>
<p>
 This endpoint serves the OpenAPI description of the writable TUW API.
 The human-readable document below is also available in machine-readable
 form:
</p>
<div class="links">
 <a href="{safe(yaml_url)}"><code>?format=yaml</code> (YAML)</a>
 <a href="{safe(json_url)}"><code>?format=json</code> (JSON)</a>
</div>
<hr>
<pre>{safe(description)}</pre>
</body>
</html>
"""
        return html.encode("utf-8")

    @staticmethod
    def _strip_query(request):
        """Return the request path (without the query string)."""
        return request.get_full_path().split("?", 1)[0]


class TUWSchemaView(SpectacularAPIView):
    """
    Public (no-auth) OpenAPI 3 document for the writable TUW API, served
    at /api/tuw/schema/.

    Only the writable TUW endpoints are documented: the view generates
    its schema from the ``api.tuw.urls`` urlconf exclusively (see
    ``urlconf``) and re-prefixes the paths, so the document never drifts
    from the actual URL routing. The schema endpoint itself is not part
    of that urlconf.

    Negotiation:
    - no ``?format`` and no specific OpenAPI Accept header → ``text/html``
      (the HTML renderer is listed first, so it wins against ``*/*``).
    - ``?format=yaml`` / ``?format=json`` → the corresponding document,
      via DRF's built-in ``URL_FORMAT_OVERRIDE``.
    - explicit ``Accept: application/vnd.oai.openapi(+json)`` → YAML/JSON.
    """

    # HTML first so a browser (or an unprefixed ``?format`` request with a
    # generic Accept) gets the human-readable page by default; the YAML and
    # JSON renderers remain available via ``?format`` or explicit Accept.
    renderer_classes = [
        TUWOpenApiHtmlRenderer,
        OpenApiYamlRenderer,
        OpenApiYamlRenderer2,
        OpenApiJsonRenderer,
        OpenApiJsonRenderer2,
    ]

    # Generate from this module's urlpatterns (issues + submissions),
    # not the site-wide urlconf.
    urlconf = "api.tuw.urls"
    # The module above defines bare path segments; the actual mount point
    # is /api/tuw/ (see core.include_urls). Re-add the prefix so the
    # operation paths match the real URLs.
    custom_settings = {
        "TITLE": "Janeway TUW Writable API",
        "DESCRIPTION": (
            "Machine-to-machine writable API used by TUW to create and "
            "update issues and submissions on a Janeway journal. All "
            "endpoints are scoped to the journal resolved from the "
            "request domain and require a shared API key sent as "
            "'Authorization: Bearer <TUW_API_KEY>' (see the 'TuwBearer' "
            "security scheme). Responses reuse the readable API "
            "serializers, so clients can round-trip the JSON fetched "
            "from /api/."
        ),
        "VERSION": "1.0.0",
        "SCHEMA_PATH_PREFIX_INSERT": "/api/tuw",
    }
