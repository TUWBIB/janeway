import hmac

from django.conf import settings

from rest_framework import permissions
from rest_framework.exceptions import NotAuthenticated, NotFound

from utils.logger import get_logger

logger = get_logger(__name__)


class IsTUWAPIKey(permissions.BasePermission):
    """
    Permission for the writable TUW API.

    Machine-to-machine access, scoped to the journal resolved from the
    request domain by the site middleware (``request.journal``). The
    request must carry an ``Authorization: Bearer <key>`` header where
    ``<key>`` matches ``settings.TUW_API_KEY`` (same scheme as
    ``api.views.callback_link_nz_job``). Requests without a valid key
    are rejected with a 401, and requests that are not bound to a
    journal (e.g. press domain) are rejected with a 404.
    """

    message = (
        "Authentication credentials were not provided, or were not "
        'valid. Expected an "Authorization: Bearer <key>" header.'
    )

    def has_permission(self, request, view):
        expected_key = settings.TUW_API_KEY
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")

        provided_key = None
        if auth_header.startswith("Bearer "):
            provided_key = auth_header.split(" ", 1)[1]

        if (
            not expected_key
            or not provided_key
            or not hmac.compare_digest(provided_key, expected_key)
        ):
            logger.warning(
                "Rejected %s %s: missing or invalid API key",
                request.method,
                request.path,
            )
            raise NotAuthenticated(detail=self.message)

        if not getattr(request, "journal", None):
            # e.g. press domain: there is no journal to write to
            raise NotFound(
                detail="This writable API is only available on a journal domain."
            )

        return True
