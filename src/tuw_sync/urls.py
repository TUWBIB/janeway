from django.urls import re_path
from django.conf import settings

from tuw_sync import views

urlpatterns = [
    re_path(r'^tuw_sync/$',
        views.sync,
        name='tuw_sync'),
]        

if getattr(settings,'DEBUG',False):
    urlpatterns.append(re_path(r'^tuw_sync/debug$',
        views.debug,
        name='tuw_sync_debug'))
