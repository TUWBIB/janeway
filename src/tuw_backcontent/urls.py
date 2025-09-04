from django.urls import re_path

from tuw_backcontent import views

urlpatterns = [
    re_path(r'^manage/articles/backcontent/$',
        views.backcontent, name='backcontent'),

    re_path(r'^manage/articles/backcontent/article/(?P<article_id>\d+)/$',
        views.backcontent_article, name='backcontent_article'),

    re_path(r'^manage/articles/backcontent/article/(?P<article_id>\d+)/delete/$',
        views.backcontent_delete_article, name='backcontent_delete_article'),

    re_path(r'^manage/articles/backcontent/article/(?P<article_id>\d+)/authors/(?P<author_id>\d+)/delete/$',
        views.backcontent_delete_author, name='backcontent_delete_author'),

    re_path(r'^manage/articles/backcontent/article/(?P<article_id>\d+)/add_author/$',
        views.backcontent_add_author, name='backcontent_add_author'),

    re_path(r'^manage/articles/backcontent/article/(?P<article_id>\d+)/galley/(?P<galley_id>\d+)/$',
        views.backcontent_preview_xml_galley, name='backcontent_preview_xml_galley'),

    re_path(r'^manage/articles/backcontent/article/(?P<article_id>\d+)/order_authors/$',
        views.backcontent_order_authors, name='backcontent_order_authors'),

]