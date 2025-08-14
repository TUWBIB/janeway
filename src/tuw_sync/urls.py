from django.urls import re_path

from tuw_sync import views

urlpatterns = [
    re_path(r'^tuw_sync/$',
        views.sync,
        name='tuw_sync'),
]
