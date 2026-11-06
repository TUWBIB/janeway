"""
URLs for the writable TUW API, mounted at /api/tuw/ (see
``core.include_urls``).

The path segments intentionally mirror the readable API so that clients
can swap the base path and (almost) reuse the same JSON payloads:

- POST /api/tuw/issues/            create an issue
- PUT  /api/tuw/issues/<pk>/       update an issue
- POST /api/tuw/submissions/       create a submission
- PUT  /api/tuw/submissions/<pk>/  update a submission

GET  /api/tuw/schema/ serves the public OpenAPI 3 document for the
endpoints above (see ``api.tuw.views.TUWSchemaView``).

Each writable endpoint is restricted to its single HTTP method via
``http_method_names``: the generic DRF base views (``CreateAPIView``,
``RetrieveUpdateAPIView``) would otherwise also advertise GET/PATCH/
DELETE, which this API does not support. The same restriction keeps the
generated OpenAPI document in sync with the supported methods.
"""

from django.urls import path

from api.tuw import views

urlpatterns = [
    path(
        "issues/",
        views.TUWIssueCreateView.as_view(http_method_names=["post"]),
        name="tuw_issue_create",
    ),
    path(
        "issues/<int:pk>/",
        views.TUWIssueUpdateView.as_view(http_method_names=["put"]),
        name="tuw_issue_update",
    ),
    path(
        "submissions/",
        views.TUWSubmissionCreateView.as_view(http_method_names=["post"]),
        name="tuw_submission_create",
    ),
    path(
        "submissions/<int:pk>/",
        views.TUWSubmissionUpdateView.as_view(http_method_names=["put"]),
        name="tuw_submission_update",
    ),
    # Public OpenAPI document; mounted here so the TUW document is
    # generated from exactly this module's urlconf (TUWSchemaView).
    path("schema/", views.TUWSchemaView.as_view(), name="tuw_schema"),
]
