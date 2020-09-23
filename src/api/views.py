import json
import datetime
import pytz
import re

from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from rest_framework import viewsets, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework import permissions

from api import serializers, permissions as api_permissions
from core import models as core_models
from submission import models as submission_models


@api_view(['GET'])
@permission_classes((permissions.AllowAny, ))
def index(request):
    response_dict = {
        'Message': 'Welcome to the API',
        'Version': '1.0',
        'API Endpoints':
            [],
    }
    json_content = json.dumps(response_dict)

    return HttpResponse(json_content, content_type="application/json")


@permission_classes((api_permissions.IsEditor, ))
class AccountRoleViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows user roles to be viewed or edited.
    """
    queryset = core_models.AccountRole.objects.filter()
    serializer_class = serializers.AccountRoleSerializer


class JournalViewSet(viewsets.ModelViewSet):
    """
    API Endpoint for journals.
    """
    from journal import models as journal_models
    queryset = journal_models.Journal.objects.filter(hide_from_press=False)
    serializer_class = serializers.JournalSerializer
    http_method_names = ['get']


class IssueViewSet(viewsets.ModelViewSet):
    """
    API Endpoint for journals.
    """
    serializer_class = serializers.IssueSerializer
    http_method_names = ['get']

    def get_queryset(self):
        from journal import models as journal_models
        if self.request.journal:
            queryset = journal_models.Issue.objects.filter(journal=self.request.journal)
        else:
            queryset = journal_models.Issue.objects.all()

        return queryset


class LicenceViewSet(viewsets.ModelViewSet):
    """
    API Endpoint for journals.
    """
    serializer_class = serializers.LicenceSerializer
    http_method_names = ['get']

    def get_queryset(self):

        if self.request.journal:
            queryset = submission_models.Licence.objects.filter(journal=self.request.journal)
        else:
            queryset = submission_models.Licence.objects.filter(journal=self.request.press)

        return queryset


class KeywordsViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.KeywordsSerializer
    queryset = submission_models.Keyword.objects.all()
    http_method_names = ['get']

class KeywordsDeViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.KeywordsDeSerializer
    queryset = submission_models.KeywordDe.objects.all()
    http_method_names = ['get']

class ArticleViewSet(viewsets.ModelViewSet):
    """
    API Endpoint for journals.
    """
    serializer_class = serializers.ArticleSerializer
    http_method_names = ['get']

    def get_queryset(self):
        if self.request.journal:
            queryset = submission_models.Article.objects.filter(journal=self.request.journal,
                                                                stage=submission_models.STAGE_PUBLISHED,
                                                                date_published__lte=timezone.now())
        else:
            queryset = submission_models.Article.objects.filter(stage=submission_models.STAGE_PUBLISHED,
                                                                date_published__lte=timezone.now())

        return queryset


@csrf_exempt
def oai(request):
    context = {}
    context['journal'] = request.journal
    context['responseDate'] = datetime.datetime.utcnow().replace(microsecond=0).isoformat()+'Z'
    context['rv_value'] = request.scheme+'://'+request.META['HTTP_HOST']+request.path

    params = {}

    if request.method == 'GET' or request.method == 'POST':
        if request.method == 'GET': 
            for k,v in request.GET.items(): params[k] = v
        if request.method == 'POST': 
            for k,v in request.POST.items(): params[k] = v

        l = []
        for k,v in params.items():
            l.append(k + '="' + v + '"')
        context['rv_attribs'] = " ".join(l)

        print ("params----")
        for k,v in params.items():
            print (k,v)
           
        verb = None
        if 'verb' in params.keys():
            verb = params['verb']

        if verb is None or verb not in ('Identify', 'ListRecords', 'GetRecord', 'ListIdentifiers', 'ListMetadataFormats', 'ListSets'):
            return error(request,context,'badVerb')            

        elif verb == 'ListSets': return error(request,context,'noSetHierarchy')
        elif verb == 'ListRecords':
            a = set(params.keys())
            b = set(['verb', 'from', 'until', 'metadataPrefix', 'set', 'resumptionToken'])
            if not a.issubset(b): return error(request,context,'badArgument')

            from_date = params['from'] if 'from' in params else None
            until_date = params['until'] if 'until' in params else None
            metadataprefix = params['metadataPrefix'] if 'metadataPrefix' in params else None
            set_name = params['set'] if 'set' in params else None
            resumption = params['resumptionToken'] if 'resumptionToken' in params else None

            if not metadataprefix or metadataprefix == '': return error(request,context,'badArgument')
            if metadataprefix != 'oai_dc': return error(request,context,'cannotDisseminateFormat',err_val='metadataPrefix must be oai_dc')
            if set_name or set_name == '': return error(request,context,'noSetHierarchy')
            if resumption or resumption == '': return error(request,context,'badResumptionToken')
            if from_date:
                match = re.match('\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z',from_date)
                if not match: return error(request,context,'badArgument',err_val='invalid from date')
                from_date = datetime.datetime.strptime(from_date,'%Y-%m-%dT%H:%M:%SZ').replace(microsecond=0)
                print (from_date)
            if until_date:
                match = re.match('\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z',until_date)
                if not match: return error(request,context,'badArgument',err_val='invalid until date')
                until_date = datetime.datetime.strptime(until_date,'%Y-%m-%dT%H:%M:%SZ').replace(microsecond=0)
                print (until_date)

            articles = getArticles(journal=request.journal,from_date=from_date,until_date=until_date)

            if len(articles) == 0: return error(request,context,'noRecordsMatch')

            template = 'apis/OAI_ListRecords.xml'
            context['articles'] =  articles

        elif verb == 'ListIdentifiers':
            a = set(params.keys())
            b = set(['verb', 'from', 'until', 'metadataPrefix', 'set', 'resumptionToken'])
            if not a.issubset(b): return error(request,context,'badArgument')

            from_date = params['from'] if 'from' in params else None
            until_date = params['until'] if 'until' in params else None
            metadataprefix = params['metadataPrefix'] if 'metadataPrefix' in params else None
            set_name = params['set'] if 'set' in params else None
            resumption = params['resumptionToken'] if 'resumptionToken' in params else None

            if not metadataprefix or metadataprefix == '': return error(request,context,'badArgument')
            if metadataprefix != 'oai_dc': return error(request,context,'cannotDisseminateFormat',err_val='metadataPrefix must be oai_dc')
            if set_name or set_name == '': return error(request,context,'noSetHierarchy')
            if resumption or resumption == '': return error(request,context,'badResumptionToken')
            if from_date:
                match = re.match('\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z',from_date)
                if not match: return error(request,context,'badArgument',err_val='invalid from date')
                from_date = datetime.datetime.strptime(from_date,'%Y-%m-%dT%H:%M:%SZ')
            if until_date:
                match = re.match('\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z',until_date)
                if not match: return error(request,context,'badArgument',err_val='invalid until date')
                until_date = datetime.datetime.strptime(until_date,'%Y-%m-%dT%H:%M:%SZ')

            articles = getArticles(journal=request.journal,from_date=from_date,until_date=until_date)

            if len(articles) == 0: return error(request,context,'noRecordsMatch')

            template = 'apis/OAI_ListIdentifiers.xml'
            context['articles'] =  articles

        elif verb == 'ListMetadataFormats':
            a = set(params.keys())
            b = set(['verb', 'identifier'])
            if not a.issubset(b): return error(request,context,'badArgument')

            identifier = params['identifier'] if 'identifier' in params else None
            parts = identifier.split(':')
            if len(parts) != 3 or parts[0] != 'oai' or parts[1] != request.journal.domain:
                return error(request,context,'idDoesNotExist')

            doi = parts[3]
            try:
                articles = getArticles(journal=request.journal)
                article = articles[0]
            except:
                return error(request,context,'idDoesNotExist')
           
            template = 'apis/OAI_ListMetadataFormats.xml'
    
        elif verb == 'GetRecord':
            a = set(params.keys())
            b = set(['verb', 'identifier', 'metadataPrefix'])
            if not a.issubset(b): return error(request,context,'badArgument')

            identifier = params['identifier'] if 'identifier' in params else None
            metadataprefix = params['metadataPrefix'] if 'metadataPrefix' in params else None

            if not metadataprefix or metadataprefix == '': return error(request,context,'badArgument')
            if metadataprefix != 'oai_dc': return error(request,context,'cannotDisseminateFormat',err_val='metadataPrefix must be oai_dc')

            parts = identifier.split(':')
            if len(parts) != 3 or parts[0] != 'oai' or parts[1] != request.journal.domain:
                return error(request,context,'idDoesNotExist')

            doi = parts[2]
            try:
                articles = getArticles(journal=request.journal,identifier=doi)
                article = articles[0]
            except:
                return error(request,context,'idDoesNotExist')
            
            template = 'apis/OAI_GetRecord.xml'
            context['article'] = article            

        elif verb == 'Identify':
            template = 'apis/OAI_Identify.xml'
            context['repositoryName'] = request.journal.description
            context['baseURL'] = request.scheme+'://'+request.META['HTTP_HOST']+request.path
            context['adminEmail'] = 'repositum@tuwien.ac.at'
            context['deletedRecord'] = 'no'

        return render(request, template, context, content_type="text/xml")

def getArticles(journal=None,id_type='doi',identifier=None,from_date=None,until_date=None):
        articles = submission_models.Article.objects.filter(
                journal=journal,
                stage=submission_models.STAGE_PUBLISHED,
                identifier__id_type=id_type,
            )
        
        if identifier is not None:
            articles = articles.filter(identifier__identifier=identifier)

        if from_date is not None:
            articles = articles.filter(date_published__gte=from_date)

        if until_date is not None:
            articles = articles.filter(date_published__lte=until_date)

        return articles


def error(request,context,err_code,err_val=None):
    if err_val is None: err_val = err_code
    template = 'apis/OAI_Error.xml'
    context['err_code'] = err_code
    context['err_val'] = err_val
    return render(request, template, context, content_type="text/xml")

