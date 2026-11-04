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

from rest_framework import status
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


class TUWIssueCreateView(TUWCreateAPIView):
    """POST /api/tuw/issues/ — create an issue for the current journal."""

    serializer_class = tuw_serializers.IssueWriteSerializer

    def get_response_serializer(self, instance):
        return read_serializers.IssueSerializer(
            instance, context={"request": self.request}
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


class TUWSubmissionCreateView(TUWCreateAPIView):
    """POST /api/tuw/submissions/ — create a submission for the current journal."""

    serializer_class = tuw_serializers.SubmissionWriteSerializer

    def get_response_serializer(self, instance):
        return read_serializers.ArticleSerializer(
            instance, context={"request": self.request}
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
