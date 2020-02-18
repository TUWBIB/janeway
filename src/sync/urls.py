from django.conf.urls import url

from sync import views

urlpatterns = [
    url(r'^manage/articles/sync/$', views.sync, name='sync'),
]
