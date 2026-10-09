from django.shortcuts import render

# Create your views here.
import json
import traceback
import re
from typing import List
import lxml.etree as etree
import time

from django.http import HttpResponse
from django.shortcuts import render
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib.messages import get_messages
from django.contrib.contenttypes.models import ContentType
from django.templatetags.static import static
from django.core import serializers
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.urls import reverse
from django.db.models import Q, Count
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.core.management import call_command
from django.template import RequestContext, loader
from security.decorators import has_journal, editor_user_required
from submission import models as submission_models
from journal import models as journal_models
from utils.logger import get_logger
from laapy import MarcRecord,stripXmlDeclaration
from . import datacite_api,datacite_settings
from . import alma_api,alma_settings
from . import models as sync_models
from . import logic

logger = get_logger(__name__)

def debug(request):
    html = f"<h1>Debug Info</h1>"
    html += f"<p>request.scheme: {request.scheme}</p>"
    html += f"<p>request.is_secure(): {request.is_secure()}</p>"
    html += f"<p>request.get_host(): {request.get_host()}</p>"
    html += f"<p>META headers: {request.META}</p>"
    return HttpResponse(html)

## sync

@has_journal
@editor_user_required
def sync(request):
    article: submission_models.Article = None
    issue: journal_models.Issue = None
    response: JsonResponse = None

    articles = submission_models.Article.objects.filter(journal=request.journal)
    issues = journal_models.Issue.objects.filter(journal=request.journal)
    view_settings = {}
    view_settings['alma_article_sync'] = request.journal.code in alma_settings.get('article_sync',False)
    view_settings['alma_issue_sync'] = request.journal.code in alma_settings.get('issue_sync',False)
    sync_settings = datacite_settings['journals'][request.journal.code]
    view_settings['datacite_article_sync'] = 'pattern_article' in sync_settings
    view_settings['datacite_issue_sync'] = 'pattern_issue' in sync_settings

    if request.method  == "POST":
        data = json.loads(request.body)
        article_id = data['article_id']
        issue_id = data['issue_id']
        operation = data["operation"]

        if article_id:
            article = submission_models.Article.objects.filter(journal=request.journal,pk=article_id)[0]
        elif issue_id:
            issue = journal_models.Issue.objects.filter(journal=request.journal,pk=issue_id)[0]

        # Handle bulk operations
        article_ids = data.get('article_ids', [])
        if article_ids and operation in ('alma_push_nz', 'alma_push_nz_confirm', 'alma_create_update', 'alma_create_update_confirm'):
            if operation == 'alma_push_nz':
                response = almaPushNZBulk(request.journal, article_ids)
            elif operation == 'alma_push_nz_confirm':
                response = almaPushNZConfirmBulk(request.journal, article_ids)
            elif operation == 'alma_create_update':
                response = almaCreateUpdateBulk(request.journal, article_ids)
            elif operation == 'alma_create_update_confirm':
                response = almaCreateUpdateConfirmBulk(request.journal, article_ids)
            return response

        if article:
            if operation == "alma_create_update":
                response = almaCreateUpdate(article)

            elif operation == "alma_create_update_confirm":
                response = almaCreateUpdateConfirm(article)

            elif operation == "alma_push_nz":
                response = almaPushNZ(article)

            elif operation == "alma_push_nz_confirm":
                response = almaPushNZConfirm(article)

            elif operation == "alma_fetch_ac":
                response = almaFetchAC(article)

            elif operation == "alma_view_current":
                response = almaViewCurrent(article)

            elif operation == "datacite_metadata":
                response = dataciteMetadata(article_id=article_id)

            elif operation == "datacite_metadata_confirm":
                response = dataciteMetadataConfirm(article_id=article_id)

            elif operation == "datacite_url":
                response = dataciteURL(request.META['HTTP_HOST'],article=article)

            elif operation == "datacite_url_confirm":
                response = dataciteURLConfirm(request.META['HTTP_HOST'],article=article)

            elif operation == "datacite_check_metadata":
                response = getCurrentDataCiteXML(article_id=article_id)

            elif operation == "datacite_check_url":
                response = getCurrentDataCiteURL(article_id=article_id)

            elif operation == "datacite_delete_doi":
                response = deleteDOI(article=article)

        if issue:
            if operation == "datacite_metadata":
                response =  dataciteMetadata(issue_id=issue_id)

            elif operation == "datacite_metadata_confirm":
                response = dataciteMetadataConfirm(issue_id=issue_id)

            elif operation == "datacite_url":
                response = dataciteURL(request.META['HTTP_HOST'],issue=issue)

            elif operation == "datacite_url_confirm":
                response = dataciteURLConfirm(request.META['HTTP_HOST'],issue=issue)

            elif operation == "datacite_check_metadata":
                response = getCurrentDataCiteXML(issue_id=issue_id)

            elif operation == "datacite_check_url":
                response = getCurrentDataCiteURL(issue_id=issue_id)

            elif operation == "datacite_delete_doi":
                response = deleteDOI(issue=issue)

        if not response:
            errors = []
            errors.append("invalid operation")
            response = JsonResponse({ 'errors': errors, 'warnings': None,
                'datacite' : { 'xml' : None, 'doi' : None, 'url' : None, 'state' : None }})
        
        return response

    template = 'tuw_sync/sync_articles.html'
    context = {
        'articles': articles,
        'issues': issues,
        'settings': view_settings,
    }

    return render(request, template, context)

def getCurrentDataCiteXML(article_id=None,issue_id=None):
    (xml,errors,warnings) = logic.getCurrentDataCiteXML(article_id=article_id,issue_id=issue_id)

    return JsonResponse({ 'errors': errors, 'warnings': warnings,
        'datacite' : { 'xml' : xml, 'doi' : None, 'url' : None, 'state' : None }})

def getCurrentDataCiteURL(article_id=None,issue_id=None):
    (url,errors,warnings) = logic.getCurrentDataCiteURL(article_id=article_id,issue_id=issue_id)

    return JsonResponse({ 'errors': errors, 'warnings': warnings,
        'datacite' : { 'xml' : None, 'doi' : None, 'url' : url, 'state' : None }})


def dataciteMetadata(article_id=None,issue_id=None):
    (xml,errors,warnings) = logic.dataciteMetadata(article_id=article_id,issue_id=issue_id)
    return JsonResponse({ 'errors': errors, 'warnings': warnings,
        'datacite' : { 'xml' : xml, 'doi' : None, 'url' : None, 'state' : None }})


def dataciteMetadataConfirm(article_id=None,issue_id=None):
    (xml,errors,_) = logic.dataciteMetadata(article_id=article_id,issue_id=issue_id)
    if errors:
        return JsonResponse({ 'errors': errors, 'warnings': None,
            'datacite' : { 'xml' : xml, 'doi' : None, 'url' : None, 'state' : None }})
    
    match = re.search(r'<identifier\sidentifierType="DOI">(.+)</identifier>',xml)
    if match is None:
        errors = ['cant extract DOI from xml']
        return JsonResponse({ 'errors': errors, 'warnings': None,
            'datacite' : { 'xml' : xml, 'doi' : None, 'url' : None, 'state' : None }})
    else:
        doi = match.group(1)
        (status,content) = datacite_api.updateMetadata(doi,xml)
        if status == "success":
            status,errors,state = logic.metadataUpdated(doi,article_id=article_id,issue_id=issue_id)
            return JsonResponse({ 'errors': errors, 'warnings': None,
                'datacite' : { 'xml' : xml, 'doi' : doi, 'url' : None, 'state' : state }})
        else:
            errors=[]
            errors.append(content)
            return JsonResponse({ 'errors': errors, 'warnings': None,
                'datacite' : { 'xml' : xml, 'doi' : None, 'url' : None, 'state' : None }})

def dataciteURL(host,article=None,issue:journal_models.Issue=None):
    ''' 
    generates a url for datacite to be confirmed by the user
    url is set to article or issue page    
    '''
    errors = []
    url = datacite_api.options['protocol']
    url += host
    if article:
        url += reverse('article_view',args=['id',article.pk])
        doi = article.get_doi()
        if doi is None:
            errors.append("no doi registered yet")
        else:
            if not logic.checkDOI(doi,article):
                errors.append("existing DOI doesn't conform to current configuration")
        if article.datacite_state == submission_models.DATACITE_STATE_FINDABLE:
            errors.append("URL already registered")
    if issue:
        url += reverse('journal_issue',args=[issue.pk])
        doi = issue.doi
        if doi is None:
            errors.append("no doi registered yet")
        datacite = sync_models.DataCite.objects.get(issue=issue)
        if datacite and datacite.status == sync_models.DataCite.DATACITE_STATUS_FINDABLE:
            errors.append("URL already registered")

    return JsonResponse({ 'errors': errors, 'warnings': None,
        'datacite' : { 'xml' : None, 'doi' : None, 'url' : url, 'state' : None }})

def dataciteURLConfirm(host,article=None,issue=None):
    errors = []
    url = datacite_api.options['protocol']
    url += host
    if article:
        url += reverse('article_view',args=['id',article.pk])
        doi = article.get_doi()
        if doi is None:
            errors.append("no doi registered yet")
        else:
            if not logic.checkDOI(doi,article):
                errors.append("existing DOI doesn't conform to current configuration")

        if article.datacite_state == submission_models.DATACITE_STATE_FINDABLE:
            errors.append("URL already registered")
    if issue:
        url += reverse('journal_issue',args=[issue.pk])
        doi = issue.doi
        if doi is None:
            errors.append("no doi registered yet")
        datacite = sync_models.DataCite.objects.get(issue=issue)
        if datacite and datacite.status == sync_models.DataCite.DATACITE_STATUS_FINDABLE:
            errors.append("URL already registered")

    if errors:
        return JsonResponse({ 'errors': errors, 'warnings': None,
            'datacite' : { 'xml' : None, 'doi' : None, 'url' : url, 'state' : None }})

    (status,content) = datacite_api.registerURL(doi,url)
    if status == "success":
        status,errors = logic.urlSet(doi,article=article,issue=issue)
        return JsonResponse({ 'errors': errors, 'warnings': None,
            'datacite' : { 'xml' : None, 'doi' : None, 'url' : url, 'state' : submission_models.DATACITE_STATE_FINDABLE }})
    else:
        errors=[]
        errors.append(content)
        return JsonResponse({ 'errors': errors, 'warnings': None,
            'datacite' : { 'xml' : None, 'doi' : None, 'url' : url, 'state' : None }})

def deleteDOI(article: submission_models.Article = None,
              issue: journal_models.Issue = None):

    errors: List[str] = []
    if article:
        doi = article.get_doi()
        state = article.datacite_state
        if state is None or state != submission_models.DATACITE_STATE_DRAFT:
            errors.append("Unexpected state, needs to be 'Draft'")
        if doi is None:
            errors.append("No DOI registered")
        else:
            if not logic.checkDOI(doi,article):
                errors.append("existing DOI doesn't conform to current configuration")
        if errors:
            return JsonResponse({ 'errors': errors, 'warnings': None,
                'datacite' : { 'xml' : None, 'doi' : None, 'url' : None, 'state' : None }})
    if issue:
        doi = issue.doi
        datacite = sync_models.DataCite.objects.get(issue=issue)
        if not datacite or datacite.status != sync_models.DataCite.DATACITE_STATUS_DRAFT:
            errors.append("Unexpected state, needs to be 'Draft'")
        if doi is None:
            errors.append("No DOI registered")
        if errors:
            return JsonResponse({ 'errors': errors, 'warnings': None,
                'datacite' : { 'xml' : None, 'doi' : None, 'url' : None, 'state' : None }})
    
    (status,content)=api.deleteDOI(doi)
    if status == "success":
        status,errors = logic.doiDeleted(doi,article=article,issue=issue)
        if article:
            return JsonResponse({ 'errors': errors, 'warnings': None,
                'datacite' : { 'xml' : None, 'doi' : '', 'url' : None, 'state' : submission_models.DATACITE_STATE_NONE }})
        elif issue:
            return JsonResponse({ 'errors': errors, 'warnings': None,
                'datacite' : { 'xml' : None, 'doi' : '', 'url' : None, 'state' : sync_models.DataCite.DATACITE_STATUS_NONE }})

    else:
        errors=[]
        errors.append(content)
        return JsonResponse({ 'errors': errors, 'warnings': None,
            'datacite' : { 'xml' : None, 'doi' : None, 'url' : None, 'state' : None }})


def almaViewCurrent(article):
    errors = []
    mmsid = article.get_mmsid()
    ac = article.get_ac()

    if mmsid is None:
        errors.append("article has no mmsid")
        return JsonResponse({ 'errors': errors, 'warnings': None,
            'alma' : { 'xml' : None, 'mmsid' : mmsid, 'ac' : ac }})
        
    result = alma_api.getBibRecord(mmsid)
    xml = result.data
    errors = result.errs
    if errors:
        return JsonResponse({ 'errors': errors, 'warnings': None,
            'alma' : { 'xml' : None, 'mmsid' : mmsid, 'ac' : None }})

    xml = stripXmlDeclaration(xml)
    x = etree.fromstring(xml)
    xml = etree.tostring(x, pretty_print=True).decode("utf-8")
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'+xml

    return JsonResponse({ 'errors': errors, 'warnings': None,
        'alma' : { 'xml' : xml, 'mmsid' : mmsid, 'ac' : ac }})


def almaCreateUpdate(article):
    (xml,errors,warnings) = logic.articleToMarc(article)

    return JsonResponse({ 'errors': errors, 'warnings': warnings,
        'alma' : { 'xml' : xml, 'mmsid' : None, 'ac' : None }})


def almaCreateUpdateConfirm(article):
    errors = []

    mmsid = article.get_mmsid()
    ac = article.get_ac()
    doi = article.get_doi()

    portfolio_settings = alma_settings.get('portfolios',{})
    collectionid = portfolio_settings.get('collection_id',None)
    serviceid = portfolio_settings.get('service_id',None)
    create_portfolio = True if not mmsid and bool(portfolio_settings.get('create_portfolios',False)) else False

    (xml,errors,warnings) = logic.articleToMarc(article)
    if errors:
        return JsonResponse({ 'errors': errors, 'warnings': None,
            'alma' : { 'xml' : xml, 'mmsid' : mmsid, 'ac' : ac }})
    
    if mmsid:
        result = alma_api.getBibRecord(mmsid)
        xml_current = result.data
        errors = result.errs
        if errors:
            return JsonResponse({ 'errors': errors, 'warnings': warnings,
                'alma' : { 'xml' : None, 'mmsid' : mmsid, 'ac' : None }})

        match = re.search(r'<linked_record_id type="NZ">(\d+)</linked_record_id>',xml_current)
        if match:
            mmsid_nz = match[1]
            errors.append("can't update record; already in NZ: " + mmsid_nz)
            return JsonResponse({ 'errors': errors, 'warnings': warnings,
                'alma' : { 'xml' : None, 'mmsid' : mmsid, 'ac' : None }})

        result = alma_api.updateBibRecord(xml,mmsid)
    else:
        result = alma_api.createBibRecord(xml)
    
    xml = result.data
    errors = result.errs
    if errors:
        return JsonResponse({ 'errors': errors, 'warnings': warnings,
            'alma' : { 'xml' : None, 'mmsid' : mmsid, 'ac' : None }})

    try:
        xml = stripXmlDeclaration(xml)
        mr = MarcRecord()
        mr.parse(xml)
        mmsid = mr.getMMSId()
    except Exception as e:
        errors.append('error parsing API response')
        errors.append(str(e))
        return JsonResponse({ 'errors': errors, 'warnings': None,
            'alma' : { 'xml' : None, 'mmsid' : mmsid, 'ac' : ac }})

    errors = logic.setMMSId(article,mmsid)
    if errors:
        return JsonResponse({ 'errors': errors, 'warnings': None,
            'alma' : { 'xml' : xml, 'mmsid' : mmsid, 'ac' : None }})

    if create_portfolio and collectionid and serviceid:
        result = alma_api.createPortfolio(collectionid,serviceid,mmsid,f"https://doi.org/{doi}")

    errors = result.errs

    return JsonResponse({ 'errors': errors, 'warnings': None,
        'alma' : { 'xml' : xml, 'mmsid' : mmsid, 'ac' : None }})


def almaPushNZ(article):
    errors = []

    mmsid = article.get_mmsid()
    ac = article.get_ac()

    if not mmsid:
        errors.append("record has no (local) mmsid, can't push to NZ")
        return JsonResponse({ 'errors': errors, 'warnings': None,
            'alma' : { 'xml' : None, 'mmsid' : mmsid, 'ac' : ac }})
    
    result = alma_api.getBibRecord(mmsid)
    xml = result.data
    errors = result.errs
    if errors:
        return JsonResponse({ 'errors': errors, 'warnings': None,
            'alma' : { 'xml' : None, 'mmsid' : mmsid, 'ac' : None }})

    match=re.search(r'<linked_record_id type="NZ">(\d+)</linked_record_id>',xml)
    if match:
        mmsid_nz=match[1]
        errors.append("can't push record to NZ; already in NZ: "+mmsid_nz)
        return JsonResponse({ 'errors': errors, 'warnings': None,
            'alma' : { 'xml' : None, 'mmsid' : mmsid, 'ac' : None }})
    
    return JsonResponse({ 'errors': None, 'warnings': None,
        'alma' : { 'xml' : None, 'mmsid' : mmsid, 'ac' : None }})


def almaPushNZConfirm(article):
    errors = []

    mmsid = article.get_mmsid()
    ac = article.get_ac()

    if not mmsid:
        errors.append("record has no (local) mmsid, can't push to NZ")
        return JsonResponse({ 'errors': errors, 'warnings': None,
            'alma' : { 'xml' : None, 'mmsid' : mmsid, 'ac' : ac }})
    
    result = alma_api.getBibRecord(mmsid)
    xml = result.data
    errors = result.errs
    if errors:
        return JsonResponse({ 'errors': errors, 'warnings': None,
            'alma' : { 'xml' : None, 'mmsid' : mmsid, 'ac' : ac }})

    match=re.search(r'<linked_record_id type="NZ">(\d+)</linked_record_id>',xml)
    if match:
        mmsid_nz=match[1]
        errors.append("can't push record to NZ; already in NZ: "+mmsid_nz)
        return JsonResponse({ 'errors': errors, 'warnings': None,
            'alma' : { 'xml' : None, 'mmsid' : mmsid, 'ac' : ac }})


    # from here on out actual network zone push
    # 1. create set
    # 2. add bib record to set
    # 3. call job
    # 4. delete set XXX not possible until job has run

    setid, result = alma_api.createItemizedBibRecordSet(setname='JW set - '+mmsid)
    errors = result.errs
    if errors:
        errors.insert(0,'error creating set')
        return JsonResponse({ 'errors': errors, 'warnings': None,
            'alma' : { 'xml' : None, 'None' : mmsid, 'ac' : ac }})

    result = alma_api.addIdToSet(setid,mmsid)
    errors = result.errs
    if errors:
        errors.insert(0,'error adding record to set')
        return JsonResponse({ 'errors': errors, 'warnings': None,
            'alma' : { 'xml' : None, 'None' : mmsid, 'ac' : ac }})

    site_url = article.journal.site_url()
    if not site_url[-1] == '/':
        site_url += '/'
    callback_url = site_url + 'api/tuw/callback_link_nz_job/'
   
    data = {
        'setid': setid,
        'mmsids': [
            mmsid,
        ],
        'callback_url': callback_url
    }
    name = 'Janeway ' + json.dumps(data)
    result = alma_api.runLinkJob(setid,name=name)
    errors = result.errs
    if errors:
        msg = ','.join(errors)    
        errors.insert(0,'error running linking job')
        return JsonResponse({ 'errors': errors, 'warnings': None,
            'alma' : { 'xml' : None, 'None' : mmsid, 'ac' : ac }})

#    (xml,errors) = alma_api.deleteSet(setid)
#    if errors:
#        errors.insert(0,'error deleting set')
#        return JsonResponse({ 'errors': errors, 'warnings': None,
#            'alma' : { 'xml' : None, 'None' : mmsid, 'ac' : ac }})
#
  
    return JsonResponse({ 'errors': None, 'warnings': None,
        'alma' : { 'xml' : None, 'mmsid' : mmsid, 'ac' : None }})

def almaFetchAC(article):
    errors = []
    mmsid = article.get_mmsid()
    ac = article.get_ac()

    if not mmsid:
        errors.append("record has no local mmsid, create record!")
        return JsonResponse({ 'errors': errors, 'warnings': None,
            'alma' : { 'xml' : None, 'mmsid' : mmsid, 'ac' : ac }})
    
    result = alma_api.getBibRecord(mmsid)
    xml = result.data
    errors = result.errs
    if errors:
        return JsonResponse({ 'errors': errors, 'warnings': None,
            'alma' : { 'xml' : None, 'mmsid' : mmsid, 'ac' : None }})

    match=re.search(r'<linked_record_id type="NZ">(\d+)</linked_record_id>',xml)
    if not match:
        errors.append("record has no NZ mmsid, push to NZ!: ")
        return JsonResponse({ 'errors': errors, 'warnings': None,
            'alma' : { 'xml' : None, 'mmsid' : mmsid, 'ac' : None }})
    
    try:
        xml = stripXmlDeclaration(xml)
        mr = MarcRecord()
        mr.parse(xml)
        ac = mr.getAC()
    except Exception as e:
        errors.append('error parsing API response')
        errors.append(str(e))
        return JsonResponse({ 'errors': errors, 'warnings': None,
            'alma' : { 'xml' : None, 'mmsid' : mmsid, 'ac' : ac }})

    errors = logic.setAC(article,ac)

    return JsonResponse({ 'errors': errors, 'warnings': None,
        'alma' : { 'xml' : None, 'mmsid' : mmsid, 'ac' : ac }})


def almaPushNZBulk(journal, article_ids):
    """
    Check selected articles for NZ push readiness.
    Returns validation results for each article.
    """
    errors_by_id = {}
    warnings_by_id = {}
    valid_count = 0
    invalid_count = 0

    articles = submission_models.Article.objects.filter(journal=journal, pk__in=article_ids)

    for article in articles:
        mmsid = article.get_mmsid()
        article_errors = []

        if not mmsid:
            article_errors.append(f"Article {article.pk}: record has no (local) mmsid, can't push to NZ")
            errors_by_id[article.pk] = article_errors
            invalid_count += 1
            continue

        result = alma_api.getBibRecord(mmsid)
        xml = result.data
        article_errors = result.errs

        if article_errors:
            errors_by_id[article.pk] = article_errors
            invalid_count += 1
            continue

        match = re.search(r'<linked_record_id type="NZ">(\d+)</linked_record_id>', xml)
        if match:
            mmsid_nz = match[1]
            article_errors.append(f"Article {article.pk}: can't push record to NZ; already in NZ: {mmsid_nz}")
            errors_by_id[article.pk] = article_errors
            invalid_count += 1
            continue

        valid_count += 1

    if invalid_count > 0:
        return JsonResponse({
            'errors': errors_by_id,
            'warnings': None,
            'valid_count': valid_count,
            'invalid_count': invalid_count,
            'bulk': True
        })

    return JsonResponse({
        'errors': None,
        'warnings': None,
        'valid_count': valid_count,
        'invalid_count': 0,
        'bulk': True
    })


def almaPushNZConfirmBulk(journal, article_ids):
    """
    Push selected articles to Network Zone in bulk.
    Creates a single set with all valid mmsids and runs the link job.
    """
    errors = []
    success_count = 0
    failed_count = 0
    failed_articles = []

    articles = submission_models.Article.objects.filter(journal=journal, pk__in=article_ids)

    valid_mmsids = []

    for article in articles:
        mmsid = article.get_mmsid()

        if not mmsid:
            failed_count += 1
            failed_articles.append(f"Article {article.pk}: no (local) mmsid")
            continue

        result = alma_api.getBibRecord(mmsid)
        xml = result.data
        article_errors = result.errs

        if article_errors:
            failed_count += 1
            failed_articles.append(f"Article {article.pk}: {', '.join(article_errors)}")
            continue

        match = re.search(r'<linked_record_id type="NZ">(\d+)</linked_record_id>', xml)
        if match:
            mmsid_nz = match[1]
            failed_count += 1
            failed_articles.append(f"Article {article.pk}: already in NZ: {mmsid_nz}")
            continue

        valid_mmsids.append(mmsid)
        success_count += 1

    if failed_count == len(articles):
        return JsonResponse({
            'errors': failed_articles,
            'warnings': None,
            'success_count': 0,
            'failed_count': failed_count,
            'bulk': True
        })

    if not valid_mmsids:
        return JsonResponse({
            'errors': failed_articles,
            'warnings': None,
            'success_count': 0,
            'failed_count': failed_count,
            'bulk': True
        })

    # Use the first article's journal for site_url
    first_article = list(articles)[0]
    site_url = first_article.journal.site_url()
    if not site_url[-1] == '/':
        site_url += '/'
    callback_url = site_url + 'api/tuw/callback_link_nz_job/'

    # Create a single set for all valid mmsids
    setid, result = alma_api.createItemizedBibRecordSet(setname='JW set - bulk ' + ','.join(valid_mmsids[:3]))
    set_errors = result.errs

    if set_errors:
        set_errors.insert(0, 'error creating set')
        return JsonResponse({
            'errors': set_errors,
            'warnings': None,
            'success_count': success_count,
            'failed_count': failed_count,
            'bulk': True
        })

    # Add all valid mmsids to the set
    for mmsid in valid_mmsids:
        result = alma_api.addIdToSet(setid, mmsid)
        if result.errs:
            failed_count += 1
            failed_articles.append(f"Article {mmsid}: error adding to set")

    # Filter out mmsids that failed to be added
    failed_mmsids_set = set()
    for a in failed_articles:
        if 'error adding to set' in a:
            parts = a.split(': ')
            if len(parts) > 1:
                failed_mmsids_set.add(parts[1])
    added_mmsids = [m for m in valid_mmsids if m not in failed_mmsids_set]

    if not added_mmsids:
        return JsonResponse({
            'errors': failed_articles,
            'warnings': None,
            'success_count': 0,
            'failed_count': failed_count + success_count,
            'bulk': True
        })

    data = {
        'setid': setid,
        'mmsids': added_mmsids,
        'callback_url': callback_url
    }
    name = 'Janeway ' + json.dumps(data)
    result = alma_api.runLinkJob(setid, name=name)
    link_errors = result.errs

    if link_errors:
        msg = ','.join(link_errors)
        link_errors.insert(0, 'error running linking job')
        return JsonResponse({
            'errors': link_errors,
            'warnings': None,
            'success_count': success_count,
            'failed_count': failed_count + success_count,
            'bulk': True
        })

    return JsonResponse({
        'errors': None,
        'warnings': failed_articles if failed_articles else None,
        'success_count': success_count,
        'failed_count': failed_count,
        'bulk': True
    })


def almaCreateUpdateBulk(journal, article_ids):
    """
    Check selected articles for Create / Update Marc Record readiness.
    Returns validation results for each article.
    """
    errors_by_id = {}
    warnings_by_id = {}
    valid_count = 0
    invalid_count = 0

    articles = submission_models.Article.objects.filter(journal=journal, pk__in=article_ids)

    for article in articles:
        mmsid = article.get_mmsid()
        article_errors = []

        if mmsid:
            # Check if already in NZ
            result = alma_api.getBibRecord(mmsid)
            xml = result.data
            article_errors = result.errs

            if article_errors:
                errors_by_id[article.pk] = article_errors
                invalid_count += 1
                continue

            match = re.search(r'<linked_record_id type="NZ">(\d+)</linked_record_id>', xml)
            if match:
                mmsid_nz = match[1]
                article_errors.append(f"Article {article.pk}: can't update record; already in NZ: {mmsid_nz}")
                errors_by_id[article.pk] = article_errors
                invalid_count += 1
                continue

        valid_count += 1

    if invalid_count > 0:
        return JsonResponse({
            'errors': errors_by_id,
            'warnings': None,
            'valid_count': valid_count,
            'invalid_count': invalid_count,
            'bulk': True
        })

    return JsonResponse({
        'errors': None,
        'warnings': None,
        'valid_count': valid_count,
        'invalid_count': 0,
        'bulk': True
    })


def almaCreateUpdateConfirmBulk(journal, article_ids):
    """
    Create / Update Marc Records for selected articles in bulk.
    """
    errors = []
    success_count = 0
    failed_count = 0
    failed_articles = []
    updated_mmsids = {}  # Track mmsids for successfully processed articles

    articles = submission_models.Article.objects.filter(journal=journal, pk__in=article_ids)

    for article in articles:
        mmsid = article.get_mmsid()
        ac = article.get_ac()
        doi = article.get_doi()

        portfolio_settings = alma_settings.get('portfolios',{})
        collectionid = portfolio_settings.get('collection_id',None)
        serviceid = portfolio_settings.get('service_id',None)
        create_portfolio = True if not mmsid and bool(portfolio_settings.get('create_portfolios',False)) else False

        (xml, article_errors, warnings) = logic.articleToMarc(article)
        if article_errors:
            failed_count += 1
            failed_articles.append(f"Article {article.pk}: {', '.join(article_errors)}")
            continue

        if mmsid:
            # Check if already in NZ
            result = alma_api.getBibRecord(mmsid)
            xml_current = result.data
            check_errors = result.errs
            if check_errors:
                failed_count += 1
                failed_articles.append(f"Article {article.pk}: {', '.join(check_errors)}")
                continue

            match = re.search(r'<linked_record_id type="NZ">(\d+)</linked_record_id>', xml_current)
            if match:
                mmsid_nz = match[1]
                failed_count += 1
                failed_articles.append(f"Article {article.pk}: can't update record; already in NZ: {mmsid_nz}")
                continue

            result = alma_api.updateBibRecord(xml, mmsid)
        else:
            result = alma_api.createBibRecord(xml)

        xml = result.data
        article_errors = result.errs
        if article_errors:
            failed_count += 1
            failed_articles.append(f"Article {article.pk}: {', '.join(article_errors)}")
            continue

        try:
            xml = stripXmlDeclaration(xml)
            mr = MarcRecord()
            mr.parse(xml)
            mmsid = mr.getMMSId()
        except Exception as e:
            failed_count += 1
            failed_articles.append(f"Article {article.pk}: error parsing API response - {str(e)}")
            continue

        errors_set_mmsid = logic.setMMSId(article, mmsid)
        if errors_set_mmsid:
            failed_count += 1
            failed_articles.append(f"Article {article.pk}: {', '.join(errors_set_mmsid)}")
            continue

        if create_portfolio and collectionid and serviceid:
            result = alma_api.createPortfolio(collectionid, serviceid, mmsid, f"https://doi.org/{doi}")

        article_errors = result.errs
        if article_errors:
            failed_count += 1
            failed_articles.append(f"Article {article.pk}: {', '.join(article_errors)}")
            continue

        success_count += 1
        updated_mmsids[article.pk] = mmsid  # Track the mmsid for successful articles

    return JsonResponse({
        'errors': failed_articles if failed_articles else None,
        'warnings': None,
        'success_count': success_count,
        'failed_count': failed_count,
        'updated_mmsids': updated_mmsids,
        'bulk': True
    })
