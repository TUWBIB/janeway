from django.urls import re_path, include

from drf_spectacular.views import SpectacularAPIView
from rest_framework import routers

from api import views
from api.oai import views as oai_views

router = routers.DefaultRouter()
router.register(r"accountrole", views.AccountRoleViewSet, "accountrole")
router.register(r"journals", views.JournalViewSet, "journal")
router.register(r"issues", views.IssueViewSet, "issue")
router.register(r"articles", views.ArticleViewSet, "article")
router.register(r"preprints", views.PreprintViewSet, "preprint")
router.register(r"licences", views.LicenceViewSet, "licence")
router.register(r"keywords", views.KeywordsViewSet, "keywords")
router.register(r"accounts", views.AccountViewSet, "accounts")

# Wire up our API using automatic URL routing.
# Additionally, we include login URLs for the browsable API.
urlpatterns = [
    re_path(r'^', include(router.urls)),
    # keep TUW impl
    re_path(r'^oai/$', views.oai_tuw, name='OAI_list_records'),
    re_path(r'^tuw/callback_link_nz_job/$', views.callback_link_nz_job, name='callback_link_nz_job'),
    # Janeway master
#    re_path(r'^oai/$', oai_views.oai_view_factory, name='OAI_list_records'),
    re_path(r'^kbart/$', views.kbart, name='kbart'),
    re_path(r'^kbart/csv$', views.kbart_csv, name='kbart'),
    # Served by drf-spectacular (title/description/version come from
    # SPECTACULAR_SETTINGS in core.janeway_global_settings).
    re_path(r'^schema/$', SpectacularAPIView.as_view(), name='openapi-schema'),
    re_path(r'^swagger_ui/$', views.swagger_ui, name='swagger_ui'),
    re_path(r'^redoc/$', views.redoc, name='redoc'),
]
