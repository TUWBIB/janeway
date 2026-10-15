import collections
import csv
import hmac
import json
import re
import warnings
import datetime
import pytz

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.db.models import Q
from django.db.models.functions import Lower
from django.contrib.auth import logout
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from utils.logger import get_logger

from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from rest_framework import permissions
from rest_framework.response import Response

from api import serializers, permissions as api_permissions
from core import models as core_models
from submission import models as submission_models
from journal import models as journal_models
from repository import models as repository_models
from identifiers import models as identifier_models
from identifiers import models as identifier_models
from tuw_sync import models as sync_models

from laapy import API,MarcRecord,stripXmlDeclaration

logger = get_logger(__name__)

@api_view(["GET"])
@permission_classes((permissions.AllowAny,))
def index(request):
    response_dict = {
        "Message": "Welcome to the API",
        "Version": "1.0",
        "API Endpoints": [],
    }
    json_content = json.dumps(response_dict)

    return HttpResponse(json_content, content_type="application/json")


class AccountViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows editors and staff to see user accounts.
    """

    permission_classes = [api_permissions.IsEditor | api_permissions.IsSectionEditor]
    serializer_class = serializers.AccountSerializer

    def get_queryset(self):
        """
        Optionally restricts the returned object to a given user,
        by filtering against a `email` query parameter in the URL.
        """
        queryset = core_models.Account.objects.all()
        search = self.request.query_params.get("search")
        if search:
            escaped = re.escape(search)
            split_term = [re.escape(word) for word in search.split(" ")]
            split_term.append(escaped)
            search_regex = "^({})$".format("|".join({name for name in split_term}))
            queryset = queryset.filter(
                Q(email__icontains=search)
                | Q(first_name__iregex=search_regex)
                | Q(last_name__iregex=search_regex)
            )
        orcid = self.request.query_params.get("orcid")
        if orcid:
            queryset = queryset.filter(
                orcid=orcid,
            )
        return queryset


@permission_classes((api_permissions.IsEditor,))
class AccountRoleViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows user roles to be viewed or edited.
    """

    queryset = core_models.AccountRole.objects.filter()
    serializer_class = serializers.AccountRoleSerializer


class JournalViewSet(viewsets.ModelViewSet):
    """
    API Endpoint for journals.
    
    When accessed via a journal domain (e.g., test.journal.example.com),
    returns only that journal. When accessed via the press domain, returns
    all journals for that press.
    """

    serializer_class = serializers.JournalSerializer
    http_method_names = ["get"]

    def get_queryset(self):
        if self.request.journal:
            queryset = journal_models.Journal.objects.filter(
                pk=self.request.journal.pk,
                hide_from_press=False,
            )
        else:
            queryset = journal_models.Journal.objects.filter(
                hide_from_press=False,
            )
        return queryset


class IssueViewSet(viewsets.ModelViewSet):
    """
    API endpoint for issues.
    """

    serializer_class = serializers.IssueSerializer
    http_method_names = ["get"]

    def get_queryset(self):
        if self.request.journal:
            queryset = journal_models.Issue.objects.filter(
                journal=self.request.journal,
            )
        else:
            queryset = journal_models.Issue.objects.filter(
                journal__hide_from_press=False,
            )

        return queryset

class LicenceViewSet(viewsets.ModelViewSet):
    """
    API Endpoint for licenses.
    """

    serializer_class = serializers.LicenceSerializer
    http_method_names = ["get"]

    def get_queryset(self):
        if self.request.journal:
            queryset = submission_models.Licence.objects.filter(
                journal=self.request.journal
            )
        else:
            queryset = submission_models.Licence.objects.filter(
                press=self.request.press
            )

        return queryset

class KeywordsViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.KeywordsSerializer
    queryset = submission_models.Keyword.objects.all()
    http_method_names = ['get']


class ArticleViewSet(viewsets.ModelViewSet):
    """
    API endpoint for articles.
    """

    serializer_class = serializers.ArticleSerializer
    http_method_names = ["get"]

    def get_queryset(self):
        if self.request.journal:
            queryset = submission_models.Article.objects.filter(
                journal=self.request.journal,
                stage=submission_models.STAGE_PUBLISHED,
                date_published__lte=timezone.now(),
            )
        else:
            queryset = submission_models.Article.objects.filter(
                stage=submission_models.STAGE_PUBLISHED,
                date_published__lte=timezone.now(),
                journal__hide_from_press=False,
            )

        return queryset


class PreprintViewSet(viewsets.ModelViewSet):
    """
    API Endpoint for preprints.
    """

    serializer_class = serializers.PreprintSerializer
    http_method_names = ["get", "post", "delete", "put"]
    permission_classes = [api_permissions.IsRepositoryManager]

    def get_serializer_class(self):
        if self.request.method in "GET":
            return serializers.PreprintSerializer
        elif self.request.method in ["POST", "PUT"]:
            return serializers.PreprintCreateSerializer
        return serializers.PreprintSerializer

    def get_queryset(self):
        preprints = repository_models.Preprint.objects.filter(
            repository=self.request.repository,
        )

        search_term = self.request.query_params.get("search")
        stage = self.request.query_params.get("stage")
        subjects = self.request.query_params.getlist("subject")

        if search_term:
            terms = [term.lower() for term in search_term.split()]

            # Title, abstract and keywords.
            matches = (
                Q(title__icontains=search_term)
                | Q(abstract__icontains=search_term)
                | Q(keywords__word=search_term)
            )

            # Author names and affiliations, on published preprints.
            from_author = (
                submission_models.FrozenAuthor.objects.filter(
                    preprint__repository=self.request.repository,
                    preprint__date_published__lte=timezone.now(),
                )
                .annotate(
                    lower_first_name=Lower("first_name"),
                    lower_middle_name=Lower("middle_name"),
                    lower_last_name=Lower("last_name"),
                )
                .filter(
                    Q(lower_first_name__in=terms)
                    | Q(lower_middle_name__in=terms)
                    | Q(lower_last_name__in=terms)
                    | Q(
                        controlledaffiliation__organization__labels__value__icontains=search_term
                    )
                    | Q(
                        controlledaffiliation__organization__custom_label__value__icontains=search_term
                    )
                )
                .values("preprint_id")
            )
            matches |= Q(pk__in=from_author)

            # Filter the repository's queryset in the database, never widening
            # it beyond the site this request is for.
            preprints = preprints.filter(
                pk__in=repository_models.Preprint.objects.filter(matches).values("pk")
            )

        if stage:
            preprints = preprints.filter(
                stage=stage,
            )

        if subjects:
            preprints = preprints.filter(
                subject__name__in=subjects,
            )

        return preprints


class PublishedPreprintViewSet(PreprintViewSet):
    http_method_names = ["get"]
    permission_classes = [
        permissions.AllowAny,
    ]

    def get_queryset(self):
        preprints = super().get_queryset()

        subjects = self.request.query_params.getlist("subject")

        filters = {
            "date_published__isnull": False,
            "stage": repository_models.STAGE_PREPRINT_PUBLISHED,
            "repository": self.request.repository,
        }

        if subjects:
            filters["subject__name__in"] = subjects

        return preprints.filter(
            **filters,
        ).order_by(
            "-date_published",
            "title",
        )


class UserPreprintsViewSet(PreprintViewSet):
    serializer_class = serializers.PreprintSerializer
    http_method_names = ["get", "post", "put"]
    permission_classes = [permissions.IsAuthenticated, api_permissions.CanEditPreprint]

    def get_serializer_class(self):
        if self.request.method in "GET":
            return serializers.PreprintSerializer
        elif self.request.method in ["POST", "PUT"]:
            return serializers.UserPreprintSerializer
        return serializers.PreprintSerializer

    def get_queryset(self):
        preprints = repository_models.Preprint.objects.filter(
            owner=self.request.user,
            repository=self.request.repository,
        )
        stage_filter = self.request.GET.get("stage")
        if stage_filter:
            preprints = preprints.filter(stage=stage_filter)
        return preprints


class PreprintLicenses(viewsets.ModelViewSet):
    serializer_class = serializers.LicenceSerializer
    http_method_names = ["get", "post", "delete"]
    permission_classes = [
        api_permissions.IsRepositoryManager | api_permissions.IsEditor,
    ]

    def get_queryset(self):
        if self.request.repository:
            return self.request.repository.active_licenses.all()
        else:
            raise NotImplementedError(
                "This view only works with Repositories.",
            )


class RepositoryFields(viewsets.ModelViewSet):
    serializer_class = serializers.RepositoryFieldSerializer
    http_method_names = ["get"]
    permission_classes = [
        api_permissions.IsRepositoryManager,
    ]

    def get_queryset(self):
        if self.request.repository:
            return repository_models.RepositoryField.objects.filter(
                repository=self.request.repository,
            )
        else:
            raise NotImplementedError(
                "This view only works with Repositories.",
            )


class PreprintFiles(viewsets.ModelViewSet):
    serializer_class = serializers.PreprintFileSerializer
    http_method_names = ["get", "post", "delete"]
    permission_classes = [permissions.IsAuthenticated, api_permissions.CanEditPreprint]

    def get_serializer_class(self):
        if self.request.method in ["POST"]:
            return serializers.PreprintFileCreateSerializer
        return serializers.PreprintFileSerializer

    def get_queryset(self):
        if self.request.repository:
            return repository_models.PreprintFile.objects.filter(
                preprint__repository=self.request.repository,
                preprint__owner=self.request.user,
            )
        else:
            raise NotImplementedError(
                "This view only works with Repositories.",
            )


class RepositorySubjects(viewsets.ModelViewSet):
    serializer_class = serializers.PreprintSubjectGroupSerializer
    http_method_names = ["get"]

    def get_queryset(self):
        return repository_models.Subject.objects.filter(
            repository=self.request.repository,
            date_published__lte=timezone.now(),
            stage=repository_models.STAGE_PREPRINT_PUBLISHED,
        )


class RepositoryVersionQueue(viewsets.ModelViewSet):
    serializer_class = serializers.VersionQueueSerializer
    http_method_names = ["get", "post"]
    permission_classes = [
        permissions.IsAuthenticated,
    ]

    def get_serializer_class(self):
        if self.request.method in "GET":
            return serializers.VersionQueueSerializer
        elif self.request.method in ["POST"]:
            return serializers.VersionQueueCreateSerializer
        return serializers.VersionQueueSerializer

    def get_queryset(self):
        version_queues = (
            repository_models.VersionQueue.objects.filter(
                preprint__repository=self.request.repository,
                preprint__owner=self.request.user,
                is_draft=False,
            )
            .select_related("preprint", "file")
            .prefetch_related(
                "frozenauthor_set__author",
                "repositoryfieldanswer_set__field",
            )
        )
        preprint_filter = self.request.GET.get("preprint", "")
        if preprint_filter.isdigit():
            version_queues = version_queues.filter(preprint=preprint_filter)
        return version_queues


class SubmissionAccountSearch(viewsets.ModelViewSet):
    """
    Limited search feature for authenticated users. Can search by
    exact email or exact ORCID. Returns 0 results if no exact match.

    The availability of this view is controlled by the Django setting:
    API_ENABLE_ACCOUNT_ENDPOINTS which is False by default.
    """

    serializer_class = serializers.SubmissionAccountSearch
    http_method_names = ["get"]
    permission_classes = [
        permissions.IsAuthenticated,
    ]

    def get_queryset(self):
        search = self.request.GET.get("search")
        if not search:
            return core_models.Account.objects.none()
        return core_models.Account.objects.filter(
            Q(email=search) | Q(orcid=search),
        )[:1]


class UserInfo(AccountViewSet):
    """
    Account viewset limited to a single payload based on the current user.
    """

    http_method_names = ["get"]
    permission_classes = [
        permissions.IsAuthenticated,
    ]

    def get_queryset(self):
        accounts = super().get_queryset()
        accounts = accounts.filter(
            pk=self.request.user.pk,
        )
        return accounts


class Logout(viewsets.ViewSet):
    """
    A ViewSet for logging out the current user.
    """

    http_method_names = ["post"]
    permission_classes = [
        permissions.IsAuthenticated,
    ]

    @staticmethod
    def create(request):
        logout(request)
        return Response(
            {"detail": "Successfully logged out."},
            status=status.HTTP_200_OK,
        )


class RegisterAccount(viewsets.ModelViewSet):
    serializer_class = serializers.RegisterAccountSerializer
    http_method_names = ["post"]


class UpdateAccountView(APIView):
    serializer_class = serializers.RegisterAccountSerializer
    http_method_names = ["put"]
    permission_classes = [
        permissions.IsAuthenticated,
    ]

    def put(self, request, *args, **kwargs):
        account = get_object_or_404(
            core_models.Account,
            email=request.user.email,
        )
        data = request.data.copy()
        data.pop("email", None)
        serializer = self.serializer_class(
            account,
            data=data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )


class ActivateAccount(viewsets.ModelViewSet):
    serializer_class = serializers.ActivateAccountSerializer
    http_method_names = ["put"]

    def get_queryset(self):
        accounts = core_models.Account.objects.filter(
            confirmation_code=self.request.data.get("confirmation_code"),
            is_active=False,
        )
        return accounts


class Identifiers(viewsets.ModelViewSet):
    serializer_class = serializers.IdentifierSerializer
    http_method_names = ["get"]

    def get_queryset(self):
        preprint_id = self.request.GET.get("preprint_id")
        preprint_version_id = self.request.GET.get("preprint_version_id")
        article_id = self.request.GET.get("article_id")

        if self.request.repository:
            return self._get_repository_identifiers(
                preprint_id,
                preprint_version_id,
            )
        elif self.request.journal:
            return self._get_journal_identifiers(article_id)
        return identifier_models.Identifier.objects.none()

    def _get_repository_identifiers(self, preprint_id, preprint_version_id):
        queryset = identifier_models.Identifier.objects.filter(
            preprint_version__preprint__repository=self.request.repository,
            preprint_version__preprint__date_published__lte=timezone.now(),
            enabled=True,
        )
        if preprint_id:
            queryset = queryset.filter(
                preprint_version__preprint__pk=preprint_id,
            )
        elif preprint_version_id:
            queryset = queryset.filter(
                preprint_version__pk=preprint_version_id,
            )
        return queryset

    def _get_journal_identifiers(self, article_id):
        queryset = identifier_models.Identifier.objects.filter(
            article__journal=self.request.journal,
            article__date_published__lte=timezone.now(),
            enabled=True,
        )
        if article_id:
            queryset = queryset.filter(article__pk=article_id)
        return queryset


def oai(request):
    warnings.warn("This view is deprecated. OAI views are in api/oai/views.py")
    articles = submission_models.Article.objects.filter(
        stage=submission_models.STAGE_PUBLISHED
    )
    if request.journal:
        articles = articles.filter(journal=request.journal)

    template = "apis/OAI.xml"
    context = {
        "articles": articles,
    }

    return render(request, template, context, content_type="application/xml")

@csrf_exempt
def oai_tuw(request):
    context = {}
    context['journal'] = request.journal
    context['responseDate'] = datetime.datetime.utcnow().replace(microsecond=0).isoformat()+'Z'
    context['rv_value'] = request.scheme+'://'+request.META['HTTP_HOST']+request.path
    context['http_host'] = request.META['HTTP_HOST']

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

        verb = None
        if 'verb' in params.keys():
            verb = params['verb']

        if verb is None or verb not in ('Identify', 'ListRecords', 'GetRecord', 'ListIdentifiers', 'ListMetadataFormats', 'ListSets'):
            return error(request,context,'badVerb')            

        elif verb == 'ListSets':
            a = set(params.keys())
            b = set(['verb', 'resumptionToken'])
            if not a.issubset(b): return error(request,context,'badArgument')

            resumption = params['resumptionToken'] if 'resumptionToken' in params else None
            if resumption or resumption == '': return error(request,context,'badResumptionToken')

            template = 'apis/oai_tuw/OAI_ListSets.xml'
            
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
            if set_name == '': return error(request,context,'badArgument',err_val='invalid set name')
            if set_name and set_name != 'openaire': return error(request,context,'badArgument',err_val='invalid set name')
            if resumption or resumption == '': return error(request,context,'badResumptionToken')
            if from_date:
                from_date=match_date(from_date,'down')
                if from_date is None: return error(request,context,'badArgument',err_val='invalid from date')
            if until_date:
                until_date=match_date(until_date,'up')
                if until_date is None: return error(request,context,'badArgument',err_val='invalid until date')

            articles = getArticles(journal=request.journal,from_date=from_date,until_date=until_date)

            if len(articles) == 0: return error(request,context,'noRecordsMatch')

            template = 'apis/oai_tuw/OAI_ListRecords.xml'
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
            if set_name == '': return error(request,context,'badArgument',err_val='invalid set name')
            if set_name and set_name != 'openaire': return error(request,context,'badArgument',err_val='invalid set name')
            if resumption or resumption == '': return error(request,context,'badResumptionToken')
            if from_date:
                from_date=match_date(from_date,'down')
                if from_date is None: return error(request,context,'badArgument',err_val='invalid from date')
            if until_date:
                until_date=match_date(until_date,'up')
                if until_date is None: return error(request,context,'badArgument',err_val='invalid until date')

            articles = getArticles(journal=request.journal,from_date=from_date,until_date=until_date)

            if len(articles) == 0: return error(request,context,'noRecordsMatch')

            template = 'apis/oai_tuw/OAI_ListIdentifiers.xml'
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
           
            template = 'apis/oai_tuw/OAI_ListMetadataFormats.xml'
    
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
            
            template = 'apis/oai_tuw/OAI_GetRecord.xml'
            context['article'] = article            

        elif verb == 'Identify':
            template = 'apis/oai_tuw/OAI_Identify.xml'
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
            ).order_by('pk')

        if identifier is not None:
            articles = articles.filter(identifier__identifier=identifier)

        if from_date is not None:
            articles = articles.filter(date_published__gte=from_date)

        if until_date is not None:
            articles = articles.filter(date_published__lte=until_date)

        return articles

def error(request,context,err_code,err_val=None):
    if err_val is None: err_val = err_code
    template = 'apis/oai_tuw/OAI_Error.xml'
    context['err_code'] = err_code
    context['err_val'] = err_val
    return render(request, template, context, content_type="text/xml")

def match_date(date_str,round):
    date = None
    match = re.match(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z',date_str)
    if match:
        date = datetime.datetime.strptime(date_str,'%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=pytz.UTC)
    else:
        match = re.match(r'\d{4}-\d{2}-\d{2}T?',date_str)
        if match:
            if date_str[-1] == 'T':
                date = datetime.datetime.strptime(date_str,'%Y-%m-%dT')
            else:
                date = datetime.datetime.strptime(date_str,'%Y-%m-%d')

            if round == 'down':
                date = date.replace(hour=0,minute=0,second=0,tzinfo=pytz.UTC)
            if round == 'up':
                date = date.replace(hour=23,minute=59,second=59,tzinfo=pytz.UTC)
        

    return date

def kbart_csv(request):
    return kbart(request, tsv=False)


def kbart(request, tsv=True):
    """
    Produces KBART metadata output according to the spec:
    https://doi.org/10.1080/0361526X.2017.1309826
    @param request: the request object
    @param tsv: whether to produce a TSV file. If False then renders a CSV
    @return: a rendered CSV or TSV
    """

    # establish if we are outputting TSV or CSV
    delimiter = "\t" if tsv else ","

    response = (
        HttpResponse(content_type="text/csv")
        if delimiter == ","
        else HttpResponse(content_type="text/tsv")
    )

    response["Content-Disposition"] = (
        'attachment; filename="kbart.csv"'
        if delimiter == ","
        else 'attachment; filename="kbart.tsv"'
    )

    # header and stream objects
    has_header = False
    writer = None

    journals = journal_models.Journal.objects.filter(
        is_remote=False,
    )

    if request.journal:
        journals = journals.filter(pk=request.journal.pk)
    else:
        journals = journals.filter(hide_from_press=False)
    for journal in journals:
        kbart_embargo = journal.get_setting("kbart", "embargo_period")
        # Note that we here use an OrderedDict. This is important as the
        # field headers are generated below at the late init of the TSV or
        # CSV writer and need to be in the right order. Hence, fields should
        # be correctly ordered below.
        journal_line = collections.OrderedDict()

        journal_line["publication_title"] = journal.name
        journal_line["online_identifier"] = journal.issn
        journal_line["print_identifier"] = journal.print_issn

        issues = (
            journal.serial_issues()
            .filter(
                date__lte=timezone.now().date(),
            )
            .order_by("date")
        )

        # We here iterate over the issues.
        # Technically, this should check if issues are consecutive
        # because we should specify full date ranges for only material that
        # we definitely hold. A future revision to this code could check
        # that a whole issue is not purely composed of remote galley
        # articles and exclude that issue.
        if issues.exists():
            first_issue = issues.first()
            last_issue = issues.last()
            # the date that the first issue that we have was published
            journal_line["date_first_issue_online"] = "{:%Y-%m-%d}".format(
                first_issue.date
            )

            # the volume number of the first issue that we have
            journal_line["num_first_vol_online"] = first_issue.volume

            # the issue number of the first issue that we have
            journal_line["num_first_issue_online"] = first_issue.issue

            # The date that the last issue that we have was published,
            # this is should only be populated if the article has ceased
            # publication OR if the article publishes content after a
            # period of embargo
            if (
                journal.status == journal_models.Journal.PublishingStatus.ARCHIVED
                or kbart_embargo
            ):
                journal_line["date_last_issue_online"] = "{:%Y-%m-%d}".format(
                    last_issue.date
                )
                # the issue number of the last issue that we have
                journal_line["num_last_issue_online"] = last_issue.issue
                # the volume number of the last issue that we have
                journal_line["num_last_vol_online"] = last_issue.volume
            else:
                journal_line["date_last_issue_online"] = None
                journal_line["num_last_issue_online"] = None
                journal_line["num_last_vol_online"] = None

        else:
            # set these fields to None if there are no issues
            journal_line["date_first_issue_online"] = None
            journal_line["num_first_vol_online"] = None
            journal_line["num_first_issue_online"] = None
            journal_line["date_last_issue_online"] = None
            journal_line["num_last_vol_online"] = None
            journal_line["num_last_issue_online"] = None

        # the url of the journal
        journal_line["title_url"] = journal.site_url()

        # the first author of a monograph
        journal_line["first_author"] = None  # only for monographs (OFM)

        # the issn of the journal
        journal_line["title_id"] = journal.issn

        # Applicable to journals that publish in print but have period of
        # embargo period before publishing online
        journal_line["embargo_info"] = kbart_embargo or None

        # the type of coverage that we have available
        journal_line["coverage_depth"] = "fulltext"

        # a notes field for giving additional information
        journal_line["notes"] = None  # not needed

        # the name of the publisher which can be specific to the journal
        journal_line["publisher_name"] = journal.get_setting(
            "general", "publisher_name"
        )

        # the type of publication: either monograph or serial
        # because we have prefiltered, we only list serials here
        journal_line["publication_type"] = "serial"

        # for monographs, the print and online publication dates
        journal_line["date_monograph_published_print"] = None  # OFM
        journal_line["date_monograph_published_online"] = None  # OFM

        # the monograph volume and edition
        journal_line["monograph_volume"] = None  # OFM
        journal_line["monograph_edition"] = None  # OFM

        # the first editor of a monograph
        journal_line["first_editor"] = None  # OFM

        # this is a way of presenting the history of a title if it has
        # changed publisher hands etc.
        # we do not record this information in Janeway at present but it
        # may be useful information to store in future
        # TODO: record journal history of ISSN
        journal_line["parent_publication_title_id"] = None  # not needed
        journal_line["preceding_publication_title_id"] = None  # not needed

        # from the spec: "The access_type field is used to indicate whether
        # a publication is fee-based or Open Access.T his field has only two
        # possible values: F (free) or P (paid). F should be used only if
        # 100% of the content being described is free. If a title has a mix
        # of paid and free content, the P value should be used. If a title
        # has a mix of free and paid content that is clearly delineated by
        # volume, multiple lines can be included within a KBART file to
        # indicate the coverage ranges for each type of access."
        journal_line["access_type"] = "F"

        if not has_header:
            # init the streamwriter and write the header
            writer = csv.DictWriter(
                response, fieldnames=journal_line.keys(), delimiter=delimiter
            )
            has_header = True
            writer.writeheader()

        writer.writerow(journal_line)

    return response


def swagger_ui(request):
    template = "apis/swagger_ui.html"
    context = {"schema_url": "openapi-schema"}

    return render(request, template, context)


def redoc(request):
    template = "apis/redoc.html"
    context = {"schema_url": "openapi-schema"}

    return render(request, template, context)


@csrf_exempt
@require_POST
def callback_link_nz_job(request):
    """
    Skeleton endpoint called by Alma when a "Link to Network Zone" job has
    finished running.

    The endpoint is invoked via HTTP POST and is registered as the
    ``callback_url`` parameter of the Alma job (the ``job_name`` of the job
    carries the JSON payload). The following parameters may be supplied as
    POST data:

    - ``jobid``:       the Alma job instance id of the finished job (identifies
                       the ``BulkJob`` record created for the job).
    - ``setid``:       the Alma set id that was created for the linking job.
    - ``mmsids``:      a comma separated list of the Alma mmsids that were part
                       of the set.
    - ``callback_url``: the URL of this endpoint itself.

    The request must additionally carry an ``Authorization`` header of the
    form ``Bearer <key>`` where ``<key>`` matches ``TUW_API_KEY``
    from the settings. Requests without a valid key are rejected with a
    401 response before any further processing.

    :param request: An instance of django.http.HttpRequest
    :return: A JsonResponse acknowledging receipt of the callback.
    """

    # Simple API key check: expect "Authorization: Bearer <TUW_API_KEY>".
    expected_key = settings.TUW_API_KEY
    auth_header = request.META.get("HTTP_AUTHORIZATION", "")
    provided_key = auth_header.split(" ", 1)[1] if auth_header.startswith("Bearer ") else None
    if not expected_key or not provided_key or not hmac.compare_digest(provided_key, expected_key):
        logger.warning("Rejected link_nz_job callback with missing or invalid API key")
        return JsonResponse({"status": "error", "message": "Invalid or missing API key"}, status=401)

    jobid = request.POST.get("jobid")
    setid = request.POST.get("setid")
    mmsids = request.POST.get("mmsids")
    callback_url = request.POST.get("callback_url")

    # Validate required parameters
    if not jobid:
        logger.warning("Received link_nz_job callback without jobid")
        return JsonResponse({"status": "error", "message": "Missing required parameter: jobid"}, status=400)

    if not setid:
        logger.warning("Received link_nz_job callback without setid")
        return JsonResponse({"status": "error", "message": "Missing required parameter: setid"}, status=400)

    if not mmsids:
        logger.warning("Received link_nz_job callback without mmsids")
        return JsonResponse({"status": "error", "message": "Missing required parameter: mmsids"}, status=400)

    logger.info(
        "Received link_nz_job callback: jobid=%s, setid=%s, mmsids=%s, callback_url=%s",
        jobid,
        setid,
        mmsids,
        callback_url,
    )

    # Identify the BulkJob instance created for this job by its Alma job
    # instance id (unique). The jobid must correspond to a BulkJob that is
    # still in "started" status, otherwise the callback is rejected.
    bulk_job = sync_models.BulkJob.objects.filter(
        jobid=jobid,
        status=sync_models.BulkJob.BULKJOB_STATUS_STARTED,
    ).first()
    if bulk_job is None:
        logger.error(
            "rejecting link_nz_job callback: jobid %s does not correspond to a started BulkJob",
            jobid,
        )
        return JsonResponse(
            {"status": "error", "message": "No started bulk job found for jobid"},
            status=400,
        )

    if sync_models.BulkJob.objects.filter(
        journal=bulk_job.journal,
        name=bulk_job.name,
        status=sync_models.BulkJob.BULKJOB_STATUS_STARTED,
    ).exclude(pk=bulk_job.pk).exists():
        # Another bulk job with the same name is still running for this
        # journal, so this callback is not processed.
        logger.error(
            "aborting link_nz_job callback for jobid %s: another bulk job with the same name is running for journal %s",
            jobid,
            bulk_job.journal.pk if bulk_job.journal else None,
        )
        bulk_job.status = sync_models.BulkJob.BULKJOB_STATUS_ERROR
        bulk_job.save(update_fields=['status'])
        return JsonResponse(
            {"status": "error", "message": "Another bulk job with the same name is already running for this journal"},
            status=409,
        )

    job_error = False

    try:
        alma_settings = settings.ALMA
        alma_api = API(json_str=json.dumps(settings.LAAPY))

        result = alma_api.deleteSet(setid)
        xml, errors = result.data, result.errs
        if errors:
            logger.exception('error deleting set %s',setid)
            job_error = True
        else:
            logger.info('set %s deleted',setid)

        for mmsid in mmsids.split(','):
            logger.info('processing bib record %s',mmsid)            
            ac = None
            article = None
            result = alma_api.getBibRecord(mmsid)
            xml, errors = result.data, result.errs
            if errors:
                logger.exception('error getting bib record %s',mmsid)
                job_error = True
                continue

            match = re.search(r'<linked_record_id type="NZ">(\d+)</linked_record_id>',xml)
            if not match:
                logger.exception('error bib record not linked to nz %s',mmsid)
                job_error = True
                continue

            xml = stripXmlDeclaration(xml)
            mr = MarcRecord()
            mr.parse(xml)
            ac = mr.getAC()

            if ac is None:
                logger.exception('no ac for %s',mmsid)
                job_error = True
                continue
        
            try:
                article = submission_models.Article.objects.filter(
                    identifier__id_type='mmsid',
                    identifier__identifier=mmsid
                ).first()
            except Exception:
                logger.exception('error getting article for bib record %s',mmsid)
                job_error = True
                continue

            if article is None:
                logger.exception('no article for %s',mmsid)
                job_error = True
                continue

            try:
                identifier_models.Identifier.objects.filter(article=article,id_type='ac').delete()
                identifier_models.Identifier.objects.create(article=article,id_type='ac',identifier=ac)
            except Exception:
                logger.exception('error updating ac for bib record %s',mmsid)
                job_error = True
                continue
            
            logger.info("ac updated for bib record %s : %s",mmsid,ac)

    except Exception:
        logger.exception('error processing link_nz_callback')
        bulk_job.status = sync_models.BulkJob.BULKJOB_STATUS_ERROR
        bulk_job.save(update_fields=['status'])
        return JsonResponse({"status": "error", "message": "Error processing Link-NZ-Callback"}, status=400)

    bulk_job.status = (
        sync_models.BulkJob.BULKJOB_STATUS_SUCCESS
        if not job_error
        else sync_models.BulkJob.BULKJOB_STATUS_ERROR
    )
    bulk_job.save(update_fields=['status'])
    logger.info('BulkJob %s set to status %s', bulk_job.pk, bulk_job.status)

    return JsonResponse({"status": "ok", "message": "Successfully processed Link-NZ-Callback"}, status=200)



