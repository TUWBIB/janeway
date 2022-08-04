import json
import traceback
import re
import lxml.etree as etree
import time

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
from laapy import API,MarcRecord,stripXmlDeclaration

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
            response = articleToDataCiteXML(article_id)

        elif operation == "datacite_metadata_confirm":
            response = articleMetadataConfirm(article_id)

        elif operation == "datacite_url":
            response = dataciteURL(article,request.META['HTTP_HOST'])

        elif operation == "datacite_url_confirm":
            response = dataciteURLConfirm(article,request.META['HTTP_HOST'])

        elif operation == "datacite_check_metadata":
            response = getCurrentDataCiteXML(article_id)

        elif operation == "datacite_check_url":
            response = getCurrentDataCiteURL(article_id)

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

def getCurrentDataCiteURL(article_id):
    (url,errors,warnings) = logic.getCurrentDataCiteURL(article_id)

    return JsonResponse({ 'errors': errors, 'warnings': warnings,
        'datacite' : { 'xml' : None, 'doi' : None, 'url' : url, 'state' : None }})


def articleToDataCiteXML(article_id):
    (xml,errors,warnings) = logic.articleToDataCiteXML(article_id)

    return JsonResponse({ 'errors': errors, 'warnings': warnings,
        'datacite' : { 'xml' : xml, 'doi' : None, 'url' : None, 'state' : None }})


def articleMetadataConfirm(article_id):
    (xml,errors,_) = logic.articleToDataCiteXML(article_id)
    if errors:
        return JsonResponse({ 'errors': errors, 'warnings': None,
            'datacite' : { 'xml' : xml, 'doi' : None, 'url' : None, 'state' : None }})
    
    api = datacite_api.API(json_str=json.dumps(settings.DATACITE))
    match = re.search(r'<identifier\sidentifierType="DOI">(.+)</identifier>',xml)
    if match is None:
        errors = ['cant extract DOI from xml']
        return JsonResponse({ 'errors': errors, 'warnings': None,
            'datacite' : { 'xml' : xml, 'doi' : None, 'url' : None, 'state' : None }})
    else:
        doi = match.group(1)
        (status,content)=api.updateMetadata(doi,xml)
        if status == "success":
            status,errors,state = logic.metadataUpdated(article_id,doi)
            return JsonResponse({ 'errors': errors, 'warnings': None,
                'datacite' : { 'xml' : xml, 'doi' : doi, 'url' : None, 'state' : state }})
        else:
            errors=[]
            errors.append(content)
            return JsonResponse({ 'errors': errors, 'warnings': None,
                'datacite' : { 'xml' : xml, 'doi' : None, 'url' : None, 'state' : None }})

def dataciteURL(article,host):
    errors = []
    api = datacite_api.API(json_str=json.dumps(settings.DATACITE))
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
    api = datacite_api.API(json_str=json.dumps(settings.DATACITE))
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
    api = datacite_api.API(json_str=json.dumps(settings.DATACITE))
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


def almaViewCurrent(article):
    errors = []
    mmsid = article.get_mmsid()
    ac = article.get_ac()

    if mmsid is None:
        errors.append("article has no mmsid")
        return JsonResponse({ 'errors': errors, 'warnings': None,
            'alma' : { 'xml' : None, 'mmsid' : mmsid, 'ac' : ac }})
        
    try:
        api = API(json_str=json.dumps(settings.LAAPY))
    except Exception as e:
        errors.append('error getting Alma API instance')
        errors.append(str(e))
        return JsonResponse({ 'errors': errors, 'warnings': None,
            'alma' : { 'xml' : None, 'mmsid' : mmsid, 'ac' : ac }})

    result = api.getBibRecord(mmsid)
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

    try:
        api = API(json_str=json.dumps(settings.LAAPY))
    except Exception as e:
        errors.append('error getting Alma API instance')
        errors.append(str(e))
        return JsonResponse({ 'errors': errors, 'warnings': None,
            'alma' : { 'xml' : None, 'mmsid' : mmsid, 'ac' : ac }})

    (xml,errors,warnings) = logic.articleToMarc(article)
    if errors:
        return JsonResponse({ 'errors': errors, 'warnings': None,
            'alma' : { 'xml' : xml, 'mmsid' : mmsid, 'ac' : ac }})
    
    if mmsid:
        result = api.getBibRecord(mmsid)
        xml = result.data
        errors = result.errs
        if errors:
            return JsonResponse({ 'errors': errors, 'warnings': warnings,
                'alma' : { 'xml' : None, 'mmsid' : mmsid, 'ac' : None }})

        match=re.search('<linked_record_id type="NZ">(\d+)</linked_record_id>',xml)
        if match:
            mmsid_nz=match[1]
            errors.append("can't update record; already in NZ: "+mmsid_nz)
            return JsonResponse({ 'errors': errors, 'warnings': warnings,
                'alma' : { 'xml' : None, 'mmsid' : mmsid, 'ac' : None }})

        result = api.updateBibRecord(xml,mmsid)
    else:
        result = api.createBibRecord(xml)
    
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
    
    try:
        api = API(json_str=json.dumps(settings.LAAPY))
    except Exception as e:
        errors.append('error getting Alma API instance')
        errors.append(str(e))
        return JsonResponse({ 'errors': errors, 'warnings': None,
            'alma' : { 'xml' : None, 'mmsid' : mmsid, 'ac' : ac }})

    result = api.getBibRecord(mmsid)
    xml = result.data
    errors = result.errs
    if errors:
        return JsonResponse({ 'errors': errors, 'warnings': None,
            'alma' : { 'xml' : None, 'mmsid' : mmsid, 'ac' : None }})

    match=re.search('<linked_record_id type="NZ">(\d+)</linked_record_id>',xml)
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
    
    try:
        api = API(json_str=json.dumps(settings.LAAPY))
    except Exception as e:
        errors.append('error getting Alma API instance')
        errors.append(str(e))
        return JsonResponse({ 'errors': errors, 'warnings': None,
            'alma' : { 'xml' : None, 'mmsid' : mmsid, 'ac' : ac }})

    result = api.getBibRecord(mmsid)
    xml = result.data
    errors = result.errs
    if errors:
        return JsonResponse({ 'errors': errors, 'warnings': None,
            'alma' : { 'xml' : None, 'mmsid' : mmsid, 'ac' : ac }})

    match=re.search('<linked_record_id type="NZ">(\d+)</linked_record_id>',xml)
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

    setid, result = api.createItemizedBibRecordSet(setname='JW set - '+mmsid)
    errors = result.errs
    if errors:
        errors.insert(0,'error creating set')
        return JsonResponse({ 'errors': errors, 'warnings': None,
            'alma' : { 'xml' : None, 'None' : mmsid, 'ac' : ac }})

    result = api.addIdToSet(setid,mmsid)
    errors = result.errs
    if errors:
        errors.insert(0,'error adding record to set')
        return JsonResponse({ 'errors': errors, 'warnings': None,
            'alma' : { 'xml' : None, 'None' : mmsid, 'ac' : ac }})
   
    result = api.runLinkJob(setid)
    errors = result.errs
    if errors:
        msg = ','.join(errors)    
        print (msg)        
        errors.insert(0,'error running linking job')
        return JsonResponse({ 'errors': errors, 'warnings': None,
            'alma' : { 'xml' : None, 'None' : mmsid, 'ac' : ac }})

#    (xml,errors) = api.deleteSet(setid)
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
    
    try:
        api = API(json_str=json.dumps(settings.LAAPY))
    except Exception as e:
        errors.append('error getting Alma API instance')
        errors.append(str(e))
        return JsonResponse({ 'errors': errors, 'warnings': None,
            'alma' : { 'xml' : None, 'mmsid' : mmsid, 'ac' : ac }})

    result = api.getBibRecord(mmsid)
    xml = result.data
    errors = result.errs
    if errors:
        return JsonResponse({ 'errors': errors, 'warnings': None,
            'alma' : { 'xml' : None, 'mmsid' : mmsid, 'ac' : None }})

    match=re.search('<linked_record_id type="NZ">(\d+)</linked_record_id>',xml)
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

