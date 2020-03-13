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
from security.decorators import has_journal, editor_user_required
from submission import models as submission_models
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

        data=json.loads(request.body)
        article_id = data['article_id']
        article = submission_models.Article.objects.filter(journal=request.journal,pk=article_id)[0]
        operation = data["operation"]
        response = None

        if operation == "alma_up":
            response = articleToMarc(article)

        elif operation == "alma_up_confirm":
            pass

        elif operation == "alma_down":
            pass


        elif operation == "datacite_metadata":
            response = articleToDataCiteXML(article_id)

        elif operation == "datacite_metadata_confirm":
            response = articleMetadataConfirm(article_id)

        elif operation == "datacite_url":
            response = dataciteURL(article,request.META['HTTP_HOST'])

        elif operation == "datacite_url_confirm":
            response = dataciteURLConfirm(article,request.META['HTTP_HOST'])

        elif operation == "datacite_check_metadata":
            response = getCurrentDataCiteXML(article_id)

        elif operation == "datacite_delete_doi":
            response = deleteDOI(article)

        else:
            errors = []
            errors.append("invalid operation")
            response = JsonResponse({ 'errors': errors, 'warnings': None,
                'datacite' : { 'xml' : None, 'doi' : None, 'url' : None, 'state' : None }})
        
        return response

    template = 'journal/manage/sync/sync_articles.html'
    context = {
        'articles': articles,
    }

    return render(request, template, context)

def getCurrentDataCiteXML(article_id):
    (xml,errors,warnings) = logic.getCurrentDataCiteXML(article_id)

    return JsonResponse({ 'errors': errors, 'warnings': warnings,
        'datacite' : { 'xml' : xml, 'doi' : None, 'url' : None, 'state' : None }})

def articleToDataCiteXML(article_id):
    (xml,errors,warnings) = logic.articleToDataCiteXML(article_id)

    return JsonResponse({ 'errors': errors, 'warnings': warnings,
        'datacite' : { 'xml' : xml, 'doi' : None, 'url' : None, 'state' : None }})


def articleMetadataConfirm(article_id):
    (xml,errors,_) = logic.articleToDataCiteXML(article_id)
    if errors:
        return JsonResponse({ 'errors': errors, 'warnings': None,
            'datacite' : { 'xml' : xml, 'doi' : None, 'url' : None, 'state' : None }})
    
    api = datacite_api.API.getInstance()
    match = re.search(r'<identifier\sidentifierType="DOI">(.+)</identifier>',xml)
    if match is None:
        errors = ['cant extract DOI from xml']
        return JsonResponse({ 'errors': errors, 'warnings': None,
            'datacite' : { 'xml' : xml, 'doi' : None, 'url' : None, 'state' : None }})
    else:
        doi = match.group(1)
        (status,content)=api.updateMetadata(doi,xml)
        if status == "success":
            status,errors = logic.metadataUpdated(article_id,doi)
            return JsonResponse({ 'errors': errors, 'warnings': None,
                'datacite' : { 'xml' : xml, 'doi' : doi, 'url' : None, 'state' : submission_models.DATACITE_STATE_DRAFT }})
        else:
            errors=[]
            errors.append(content)
            return JsonResponse({ 'errors': errors, 'warnings': None,
                'datacite' : { 'xml' : xml, 'doi' : None, 'url' : None, 'state' : None }})

def dataciteURL(article,host):
    errors = []
    api = datacite_api.API.getInstance()
    url = api.options['protocol']
    url += host
    url += reverse('article_view',args=['id',article.pk])
    doi = article.get_doi()
    if doi is None:
        errors.append("no doi registered yet")
    else:
        if not api.doiConformsToCurrentConfiguration(article.journal.code,doi):
            errors.append("existing DOI doesn't conform to current configuration")
    if article.datacite_state == submission_models.DATACITE_STATE_FINDABLE:
        errors.append("URL already registered")

    return JsonResponse({ 'errors': errors, 'warnings': None,
        'datacite' : { 'xml' : None, 'doi' : None, 'url' : url, 'state' : None }})

def dataciteURLConfirm(article,host):
    errors = []
    api = datacite_api.API.getInstance()
    url = api.options['protocol']
    url += host
    url += reverse('article_view',args=['id',article.pk])
    doi = article.get_doi()
    if doi is None:
        errors.append("no doi registered yet")
    else:
        if not api.doiConformsToCurrentConfiguration(article.journal.code,doi):
            errors.append("existing DOI doesn't conform to current configuration")

    if article.datacite_state == submission_models.DATACITE_STATE_FINDABLE:
        errors.append("URL already registered")

    if errors:
        return JsonResponse({ 'errors': errors, 'warnings': None,
            'datacite' : { 'xml' : None, 'doi' : None, 'url' : url, 'state' : None }})


    (status,content)=api.registerURL(doi,url)
    if status == "success":
        status,errors = logic.urlSet(article.pk,doi)
        return JsonResponse({ 'errors': errors, 'warnings': None,
            'datacite' : { 'xml' : None, 'doi' : None, 'url' : url, 'state' : submission_models.DATACITE_STATE_FINDABLE }})
    else:
        errors=[]
        errors.append(content)
        return JsonResponse({ 'errors': errors, 'warnings': None,
            'datacite' : { 'xml' : None, 'doi' : None, 'url' : url, 'state' : None }})

def deleteDOI(article):
    errors = []
    api = datacite_api.API.getInstance()
    doi = article.get_doi()
    state = article.datacite_state
    if state is None or state != submission_models.DATACITE_STATE_DRAFT:
        errors.append("Unexpected state, needs to be 'Draft'")
    if doi is None:
        errors.append("No DOI registered")
    else:
        if not api.doiConformsToCurrentConfiguration(article.journal.code,doi):
            errors.append("existing DOI doesn't conform to current configuration")
    if errors:
        return JsonResponse({ 'errors': errors, 'warnings': None,
            'datacite' : { 'xml' : None, 'doi' : None, 'url' : None, 'state' : None }})
    
    (status,content)=api.deleteDOI(doi)
    if status == "success":
        status,errors = logic.doiDeleted(article.pk,doi)
        return JsonResponse({ 'errors': errors, 'warnings': None,
            'datacite' : { 'xml' : None, 'doi' : '', 'url' : None, 'state' : submission_models.DATACITE_STATE_NONE }})
    else:
        errors=[]
        errors.append(content)
        return JsonResponse({ 'errors': errors, 'warnings': None,
            'datacite' : { 'xml' : None, 'doi' : None, 'url' : None, 'state' : None }})


def articleToMarc(article):
    (xml,errors,warnings) = logic.articleToMarc(article)

    return JsonResponse({ 'errors': errors, 'warnings': warnings,
        'alma' : { 'xml' : xml, 'mmsid' : None, 'ac' : None }})


def articleToMarcConfirm(article):
    (xml,errors,warnings) = logic.articleToMarcConfirm(article)

    return JsonResponse({ 'errors': errors, 'warnings': warnings,
        'alma' : { 'xml' : xml, 'mmsid' : None, 'ac' : None }})

