"""
URLs for the writable TUW API, mounted at /api/tuw/ (see
``core.include_urls``).

The path segments intentionally mirror the readable API so that clients
can swap the base path and (almost) reuse the same JSON payloads:

- POST /api/tuw/issues/            create an issue
- PUT  /api/tuw/issues/<pk>/       update an issue
- POST /api/tuw/submissions/       create a submission
- PUT  /api/tuw/submissions/<pk>/  update a submission
"""

from django.urls import path

from api.tuw import views

urlpatterns = [
    path("issues/", views.TUWIssueCreateView.as_view(), name="tuw_issue_create"),
    path(
        "issues/<int:pk>/",
        views.TUWIssueUpdateView.as_view(),
        name="tuw_issue_update",
    ),
    path(
        "submissions/",
        views.TUWSubmissionCreateView.as_view(),
        name="tuw_submission_create",
    ),
    path(
        "submissions/<int:pk>/",
        views.TUWSubmissionUpdateView.as_view(),
        name="tuw_submission_update",
    ),
]
