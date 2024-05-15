from django.urls import re_path

from sync import views

urlpatterns = [
    re_path(r'^manage/articles/sync/$',
        views.sync,
        name='sync'),
]
