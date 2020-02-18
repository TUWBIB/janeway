import json
import traceback
import re
import lxml.etree as etree

from django.shortcuts import render
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib.messages import get_messages
from django.contrib.contenttypes.models import ContentType
from django.contrib.staticfiles.templatetags.staticfiles import static
from django.core import serializers
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.urls import reverse
from django.db.models import Q, Count
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.core.management import call_command
from django.template import RequestContext, loader

from core import (
    files,
    models as core_models,
    plugin_loader,
    logic as core_logic,
)
from review import forms as review_forms
from security.decorators import article_stage_accepted_or_later_required, \
    article_stage_accepted_or_later_or_staff_required, article_exists, file_user_required, has_request, has_journal, \
    file_history_user_required, file_edit_user_required, production_user_or_editor_required, \
    editor_user_required, keyword_page_enabled
from submission import models as submission_models
from submission import forms as submission_forms
from submission import logic as submission_logic
from identifiers import models as identifiers_models
from utils.logger import get_logger
from sync import logic
from sync.datacite import api as datacite_api


logger = get_logger(__name__)

## sync

@has_journal
@editor_user_required
def sync(request):
    articles = submission_models.Article.objects.filter(journal=request.journal)


    if request.method  == "POST":
        status = "success"

        data=json.loads(request.body)
        article_id = data['article_id']
        article = submission_models.Article.objects.filter(journal=request.journal,pk=article_id)[0]
        operation = data["operation"]

        if operation == "alma_down":
            pass
        elif operation == "alma_up":
            pass
        elif operation == "datacite_metadata":
            (xml,errors,warnings) = logic.article_to_DataCiteXML(article_id)
            if errors:
                status = "error"

            response = JsonResponse({'status': status, 'xml': xml, 'errors': errors, 'warnings': warnings })
            return response
        elif operation == "datacite_metadata_confirm":
            (xml,errors,_) = logic.article_to_DataCiteXML(article_id)
            if errors:
                status = "error"
                response = JsonResponse({'status': status, 'xml': xml, 'errors': errors, 'warnings': [] })
                return response
            
            api = datacite_api.API.getInstance()
            match = re.search(r'<identifier\sidentifierType="DOI">(.+)</identifier>',xml)
            if match is None:
                status = "error"
                errors = ['cant extract DOI from xml']
                response = JsonResponse({'status': status, 'xml': xml, 'errors': errors, 'doi': '' })
            else:
                doi = match.group(1)
                (status,content)=api.updateMetadata(doi,xml)
                if status == "success":
                    status,errors = logic.metadataUpdated(article_id,doi)
                    response = JsonResponse({'status': status, 'xml': xml, 'errors': errors, 'doi': doi })
                else:
                    errors=[]
                    errors.append(content)
                    response = JsonResponse({'status': status, 'xml': xml, 'errors': errors, 'doi': doi })
            return response
        elif operation == "datacite_url":
            status = "success"
            api = datacite_api.API.getInstance()
            url = api.options['protocol']
            url += request.META['HTTP_HOST']
            url += reverse('article_view',args=['id',article_id])
            response = JsonResponse({'status': status, 'url': url, 'errors': [], 'warnings': [] })
            return response
        elif operation == "datacite_url_confirm":
            status = "success"
            api = datacite_api.API.getInstance()
            url = api.options['protocol']
            url += request.META['HTTP_HOST']
            url += reverse('article_view',args=['id',article_id])
            doi = article.get_doi()

            (status,content)=api.registerURL(doi,url)
            if status == "success":
                # TODO, send response, update status
                response = JsonResponse({'status': status, 'url': url, 'errors': [] })
            else:
                errors=[]
                errors.append(content)
                response = JsonResponse({'status': status, 'url': url, 'errors': errors })
            return response



            response = JsonResponse({'status': status, 'url': url, 'errors': [], 'warnings': [] })
            return response


            pass

    template = 'journal/manage/sync/sync_articles.html'
    context = {
        'articles': articles,
    }

    return render(request, template, context)
