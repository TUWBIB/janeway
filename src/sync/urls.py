from django.conf.urls import url

from sync import views

urlpatterns = [
    url(r'^manage/articles/sync/$', views.sync, name='sync'),
    url(r'^manage/articles/sync/article/(?P<article_id>\d+)$', views.sync_article, name='sync_article'),
    url(r'^manage/articles/sync/article/(?P<article_id>\d+)/alma_down$', views.sync_article_alma_down, name='sync_article_alma_down'),
    url(r'^manage/articles/sync/article/(?P<article_id>\d+)/alma_up$', views.sync_article_alma_up, name='sync_article_alma_up'),
    url(r'^manage/articles/sync/article/(?P<article_id>\d+)/datacite_down$', views.sync_article_datacite_down, name='sync_article_datacite_down'),
    url(r'^manage/articles/sync/article/(?P<article_id>\d+)/datacite_up$', views.sync_article_datacite_up, name='sync_article_datacite_up'),
]
