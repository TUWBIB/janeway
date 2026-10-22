import json
import re

import requests

from django.shortcuts import render
from django.conf import settings
from django.contrib import messages
from django.contrib.messages import get_messages
from django.core import serializers
from django.urls import reverse
from django.http import Http404, HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone, translation
from django.utils.translation import gettext_lazy as _
from django.template import loader

from core import (
    models as core_models,
    logic as core_logic,
)

from journal import logic
from journal.logic import get_best_galley, get_galley_content
from security.decorators import (
    editor_user_required,
)
from submission import models as submission_models
from submission import forms as submission_forms
from submission import logic as submission_logic
from utils import setting_handler
from utils import shared
from utils.logger import get_logger
from utils.decorators import GET_language_override
from utils.forms import clean_orcid_id
from production import logic as prod_logic

from tuw_backcontent import forms as bc_forms

logger = get_logger(__name__)


## added TUW
## backcontent

def backcontent(request):
    if request.POST:
        article = submission_models.Article.objects.create(journal=request.journal,
                                                date_accepted=timezone.now(),
                                                is_import=True,
                                                title='')
        return redirect(reverse('backcontent_article', kwargs={'article_id': article.pk}))

    articles = submission_models.Article.objects.filter(journal=request.journal)

    template = 'tuw_backcontent/articles.html'
    context = {
        'articles': articles,
    }

    return render(request, template, context)

@GET_language_override
@editor_user_required
def backcontent_article(request, article_id):
    from production import logic as production_logic,forms as production_forms    
    with translation.override(request.override_language):
        article = get_object_or_404(
            submission_models.Article,
            pk=article_id,
            journal=request.journal,
        )
        submission_summary = setting_handler.get_setting(
            'general',
            'submission_summary',
            request.journal,
        ).processed_value

        additional_fields = submission_models.Field.objects.filter(journal=request.journal)

        if not article.license:
            default_configuration = request.journal.submissionconfiguration
            article.license = default_configuration.default_license

        article_form = submission_forms.ArticleInfo(instance=article,journal=request.journal,additional_fields=additional_fields,submission_summary=submission_summary,pop_disabled_fields=False)
        author_form = submission_forms.EditFrozenAuthor()
        pub_form = bc_forms.PublicationInfo(instance=article)
        remote_form = bc_forms.RemoteArticle(instance=article)
        galley_form = production_forms.GalleyForm()

        if request.POST:
            if 'file' in request.FILES:
                return handleFileUpload(request, article)

            if 'publish' or 'draft' in request.POST:
                article_form = submission_forms.ArticleInfo(request.POST, instance=article)                
                if article_form.is_valid():                
                    if 'publish' in request.POST:
                        handleSaveForm(request, article)
                        if not article.stage == submission_models.STAGE_PUBLISHED:
            #                id_logic.generate_crossref_doi_with_pattern(article)
                            article.stage = submission_models.STAGE_PUBLISHED
                            article.save()
                        article.snapshot_authors()

                        return redirect(reverse('backcontent'))

                    if 'draft' in request.POST:
                        handleSaveForm(request, article)
                        return redirect(reverse('backcontent'))
                else:
                    l = [f'{field.name}: {field.errors.as_text()}' for field in article_form if field.errors]
                    if l:
                        messages.error(request,'\n'.join(l))


            if 'delete' in request.POST:
                return redirect(reverse('backcontent_delete_article', kwargs={'article_id': article_id}))

    template = 'tuw_backcontent/submission.html'
    context = {
        'article': article,
        'article_form': article_form,
        'pub_form': pub_form,
        'galleys': prod_logic.get_all_galleys(article),
        'remote_form': remote_form,
        'additional_fields': additional_fields,
        'galley_form': galley_form,
        'author_form': author_form,
        'authors': submission_logic.get_current_authors(article, request),
        # shows the per-author "Create account" button in the
        # shared current_authors include
        'show_create_account_button': True,
    }

    return render(request, template, context)

@require_POST
@editor_user_required
def backcontent_create_account_for_author(request, article_id, author_id):
    """Creates an (inactive) core.Account for a detached FrozenAuthor and
    links the frozen author to the new account.

    Used by the per-author "Create account" button on the backcontent
    article page, so that backcontent articles added without a previous
    submission process can still get a corresponding author.
    """
    article = get_object_or_404(
        submission_models.Article,
        pk=article_id,
        journal=request.journal,
    )
    author = get_object_or_404(
        submission_models.FrozenAuthor, pk=author_id, article=article
    )

    if author.author:
        messages.add_message(
            request,
            messages.INFO,
            _("%(author_name)s is already linked to a user account.")
            % {"author_name": author.full_name()},
        )
    else:
        # Prefer the author's real email. If there is none (e.g. a
        # GND-only record), fall back to the placeholder scheme
        # firstname.lastname@no.valid.email.com (see
        # FrozenAuthor.account_email / placeholder_email). Such
        # accounts can still serve as the correspondence-author
        # anchor; their email simply cannot be used for delivery.
        email = author.account_email()
        if not author.real_email:
            messages.add_message(
                request,
                messages.INFO,
                _("%(author_name)s has no email address, the placeholder email %(email)s will be used.")
                % {"author_name": author.full_name(), "email": email},
            )

        account = core_models.Account.objects.filter(
            email__iexact=email
        ).first()
        if account:
            created = False
            messages.add_message(
                request,
                messages.SUCCESS,
                _("%(author_name)s is linked to the existing account %(email)s.")
                % {"author_name": author.full_name(), "email": account.email},
            )
        else:
            first_name = author.first_name or ""
            last_name = author.last_name or ""
            if not (first_name or last_name):
                first_name = first_name or "Author"
                last_name = last_name or email.split("@")[0]
            account = core_models.Account.objects.create(
                email=email,
                username=email.lower(),
                first_name=first_name,
                last_name=last_name,
                orcid=author.frozen_orcid or None,
                # intentionally inactive: the person has not
                # registered, the account is only the anchor for the
                # correspondence-author role and the article workflow.
                is_active=False,
            )
            created = True
            messages.add_message(
                request,
                messages.SUCCESS,
                _("Created inactive account %(email)s for %(author_name)s.")
                % {"email": account.email, "author_name": author.full_name()},
            )

        # grant the author role for the article's journal
        if article.journal:
            # NB: do not name the throwaway '_' here; that would
            # shadow the module-level gettext '_' for the whole
            # function and break the translated messages above.
            role, role_created = core_models.Role.objects.get_or_create(
                slug="author", defaults={"name": "Author"}
            )
            core_models.AccountRole.objects.get_or_create(
                user=account, role=role, journal=article.journal
            )

        # link the frozen author to the account (mirrors
        # FrozenAuthor.associate_with_account())
        author.author = account
        author.frozen_email = ""  # linked account, don't store this value
        author.save()

    return redirect(
        reverse(
            "backcontent_article", kwargs={"article_id": article.pk}
        )
    )

@editor_user_required
def backcontent_delete_article(request, article_id):
    article = get_object_or_404(submission_models.Article, pk=article_id, journal=request.journal)
    article.delete()
    messages.add_message(request, messages.SUCCESS, '%s deleted', article_id)
    return redirect(reverse('backcontent'))

# TODO: what do to about last_changed_author``
@editor_user_required
def backcontent_add_author(request,article_id):
    article = get_object_or_404(
        submission_models.Article,
        pk=article_id,
        journal=request.journal,
    )
    new_author_form = submission_forms.EditFrozenAuthor()
    last_changed_author = None

    if request.method == "POST":
        if "add_author" in request.POST:
            last_changed_author = submission_logic.add_new_author_from_form(
                request,
                article,
            )

        elif "search_authors" in request.POST:
            search_term = request.POST.get("author_search_text")
            author = submission_logic.add_author_from_search(search_term, request, article)
            last_changed_author = author
    
    return redirect(
        reverse("backcontent_article", kwargs={"article_id": article_id})
    )


@editor_user_required
def backcontent_add_author_from_dropdown(request, article_id):
    """
    Adds an author directly from a GND/ORCID dropdown suggestion.

    The record data is passed in by the client (see the autocomplete in
    tuw_backcontent/submission.html), so no external lookup services are
    queried. A FrozenAuthor is created locally from the forename,
    surname, orcid and first affiliation of the selected record.
    """
    article = get_object_or_404(
        submission_models.Article,
        pk=article_id,
        journal=request.journal,
    )

    if request.method != "POST":
        raise Http404

    first_name = request.POST.get('first_name', '').strip()
    surname = request.POST.get('surname', '').strip()
    orcid = request.POST.get('orcid', '').strip()
    affiliations = [a.strip() for a in request.POST.getlist('affiliations') if a.strip()]

    if orcid:
        try:
            orcid = clean_orcid_id(orcid)
        except ValueError:
            orcid = ''

    if not orcid and not first_name and not surname:
        messages.add_message(
            request,
            messages.WARNING,
            _("Incomplete author record, nothing was added."),
        )
        return redirect(reverse('backcontent_article', kwargs={'article_id': article_id}))

    author, created = None, False
    if orcid:
        # Reuse an existing author with this ORCID, if there is one.
        author, created = submission_models.FrozenAuthor.get_or_snapshot_if_orcid_found(
            orcid,
            article,
        )

    if not author and (first_name or surname):
        # No ORCID (GND-only record) or no existing match: avoid
        # duplicate entries with the same name on the article.
        name_qs = submission_models.FrozenAuthor.objects.filter(article=article)
        if surname:
            name_qs = name_qs.filter(last_name__iexact=surname)
        if first_name:
            name_qs = name_qs.filter(first_name__iexact=first_name)
        if name_qs.exists():
            author = name_qs.first()

    if not author:
        author = submission_models.FrozenAuthor(
            article=article,
            first_name=first_name,
            last_name=surname,
            order=article.next_frozen_author_order(),
        )
        if orcid:
            author.frozen_orcid = orcid
        author.save()
        created = True

        # Store the first affiliation as unstructured institution text.
        if affiliations:
            core_models.ControlledAffiliation.get_or_create_without_ror(
                institution=affiliations[0],
                frozen_author=author,
            )

    if created:
        messages.add_message(
            request,
            messages.SUCCESS,
            _("%(author_name)s is now an author.") % {
                "author_name": author.full_name(),
            },
        )
    else:
        messages.add_message(
            request,
            messages.INFO,
            _("%(author_name)s is already an author.") % {
                "author_name": author.full_name(),
            },
        )

    return redirect(
        reverse("backcontent_article", kwargs={"article_id": article_id})
    )


GND_SEARCH_URL = 'https://www2.ub.tuwien.ac.at/gnd/'
ORCID_SEARCH_URL = 'https://www2.ub.tuwien.ac.at/orcid/'
MAX_AUTHOR_SEARCH_RESULTS = 10
# Matches a full ORCID iD like 0000-0001-6872-1494 (16 chars incl. dashes).
ORCID_ID_PATTERN = re.compile(r'\d{4}-\d{4}-\d{4}-\d{3}[\dX]')


def _first_value(value):
    """Normalize GND list-valued name fields to a single string."""
    if isinstance(value, (list, tuple)):
        return ' '.join(str(v) for v in value if v).strip()
    return str(value).strip() if value else ''


def _parse_gnd_search_results(data):
    """
    Parse the LOBID GND search response (JSON-LD).

    Only person records are considered. For each person the ORCID iD is
    extracted from the ``sameAs`` list (if present).
    """
    records = []
    for member in data.get('member', []):
        types = member.get('type', [])
        if 'Person' not in types and 'DifferentiatedPerson' not in types:
            continue

        described_by = member.get('describedBy', {})
        orcid = ''
        for same in member.get('sameAs', []):
            same_id = same.get('id', '')
            if 'orcid.org/' in same_id:
                candidate = same_id.rsplit('/', 1)[-1]
                # Placeholder ORCID iDs are not real identifiers; ignoring
                # them also prevents them from collapsing distinct records
                # during orcid-based deduplication.
                if candidate.startswith('0000-0000-0000'):
                    break
                orcid = candidate
                break

        forename = _first_value(described_by.get('forename'))
        surname = _first_value(described_by.get('surname'))
        if not forename and not surname:
            # Some GND records only have a single personalName / preferredName.
            surname = _first_value(described_by.get('personalName')) or \
                _first_value(member.get('preferredName'))
        if not forename and not surname:
            continue

        records.append({
            'source': 'gnd',
            'identifier': member.get('gndIdentifier', ''),
            'orcid': orcid,
            'forename': forename,
            'surname': surname,
            'affiliations': [
                aff.get('label') for aff in member.get('affiliation', [])
                if aff.get('label')
            ],
        })
    return records


def _parse_orcid_search_results(data):
    """
    Parse the ORCID Elasticsearch search response.
    """
    records = []
    for hit in data.get('hits', {}).get('hits', []):
        source = hit.get('_source', {})
        name_entity = source.get('preferredNameEntityForThePerson', {})
        affiliation = source.get('affiliation', {}) or {}

        affiliations = []
        for key in ('emp', 'edu'):
            for value in affiliation.get(key, []) or []:
                if value not in affiliations:
                    affiliations.append(value)

        records.append({
            'source': 'orcid',
            'identifier': source.get('id') or hit.get('_id', ''),
            'orcid': source.get('id') or hit.get('_id', ''),
            'forename': _first_value(name_entity.get('forename')),
            'surname': _first_value(name_entity.get('surname')),
            'affiliations': affiliations[:3],
        })
    return records


def _fetch_search_json(url, params=None):
    """
    GET a lookup endpoint and return the parsed JSON body,
    or ``None`` on any error so that a failing lookup service does not
    break the autocomplete.
    """
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning(
            "backcontent_author_search: lookup at %s failed: %s", url, e,
        )
        return None

    try:
        return resp.json()
    except ValueError:
        logger.warning(
            "backcontent_author_search: non-JSON response from %s", url,
        )
        return None


def _fetch_author_search_results(url, search_term):
    """
    Fetch and parse one author search endpoint (``?q=<term>``).

    Returns a list of records, or an empty list on any error.
    """
    data = _fetch_search_json(url, {'q': search_term})
    if data is None:
        return []

    if url == GND_SEARCH_URL:
        return _parse_gnd_search_results(data)
    if url == ORCID_SEARCH_URL:
        return _parse_orcid_search_results(data)
    return []


def _fetch_gnd_by_orcid(orcid_id):
    """
    Fetch the GND records linked to an ORCID iD via
    ``?orcid=<iD>`` (returns the usual LOBID search shape).
    """
    data = _fetch_search_json(GND_SEARCH_URL, {'orcid': orcid_id})
    if data is None:
        return []
    return _parse_gnd_search_results(data)


def _fetch_orcid_direct(orcid_id):
    """
    Fetch a single ORCID record by iD (``/orcid/<iD>``) and parse it
    with the search-result parser.
    """
    data = _fetch_search_json(ORCID_SEARCH_URL + orcid_id)
    if data is None:
        return []

    # The direct endpoint returns a single record with the same shape
    # as the search hits' `_source`; wrap it so the search parser can
    # handle it unchanged.
    return _parse_orcid_search_results(
        {'hits': {'hits': [{'_source': data}]}}
    )


@editor_user_required
def backcontent_author_search(request):
    """
    Endpoint for the author search autocomplete.

    Queries the TUW library GND and ORCID lookup services (GND first)
    for the given search term, extracts orcid, surname, forename and
    affiliations per person, deduplicates based on orcid and returns
    at most ``MAX_AUTHOR_SEARCH_RESULTS`` records.

    When the search term is a full ORCID iD, direct lookups are used
    instead of the text search:
    * GND:   ``/gnd/?orcid=<iD>``
    * ORCID: ``/orcid/<iD>``
    """
    search_term = request.GET.get('q', '').strip()

    if not search_term:
        return JsonResponse({
            'results': [],
            'search_term': search_term,
        })

    # The client can enable/disable the individual sources via the
    # checkboxes in the dropdown search form; both are enabled by default.
    search_gnd = request.GET.get('gnd', '1') not in ('0', 'false', '')
    search_orcid = request.GET.get('orcid', '1') not in ('0', 'false', '')

    # A search term that is already a full ORCID iD is looked up directly
    # at /orcid/<iD>, which returns exactly that person's record.
    orcid_match = ORCID_ID_PATTERN.match(search_term)

    all_records = []
    if search_gnd:
        if orcid_match:
            all_records += _fetch_gnd_by_orcid(orcid_match.group(0))
        else:
            all_records += _fetch_author_search_results(GND_SEARCH_URL, search_term)
    if search_orcid:
        if orcid_match:
            all_records += _fetch_orcid_direct(orcid_match.group(0))
        else:
            all_records += _fetch_author_search_results(ORCID_SEARCH_URL, search_term)

    seen_orcids = set()
    seen_names = set()
    results = []
    for record in all_records:
        orcid = (record.get('orcid') or '').strip().lower()
        name_key = (
            record.get('surname', '').lower(),
            record.get('forename', '').lower(),
        )
        if orcid:
            if orcid in seen_orcids:
                continue
            seen_orcids.add(orcid)
        elif name_key in seen_names:
            continue
        else:
            seen_names.add(name_key)
        results.append(record)
        if len(results) >= MAX_AUTHOR_SEARCH_RESULTS:
            break

    return JsonResponse({
        'results': results,
        'search_term': search_term,
    })


@editor_user_required
def backcontent_preview_xml_galley(request, article_id, galley_id):
    """
    Allows an editor to preview an article's XML galleys.
    :param request: HttpRequest
    :param article_id: Article object ID (INT)
    :param galley_id: Galley object ID (INT)
    :return: HttpResponse
    """

    article = get_object_or_404(submission_models.Article, journal=request.journal, pk=article_id)
    galley = core_models.Galley.objects.filter(article=article, file__mime_type__contains='/xml', pk=galley_id)

    if not galley:
        raise Http404

    content = logic.list_galleys(article, galley)

    template = 'journal/article.html'
    context = {
        'article': article,
        'galleys': galley,
        'article_content': content
    }

    return render(request, template, context)


def handleFileUpload(request, article):
    from production import logic as production_logic, forms as production_forms
    context = { }
    galley = None

    galley_form = production_forms.GalleyForm(request.POST, request.FILES)
    if galley_form.is_valid():
        for index, uploaded_file in enumerate(request.FILES.getlist('file')):
            try:
                galley = production_logic.save_galley(
                    article,
                    request,
                    uploaded_file,
                    True,
                    label=galley_form.cleaned_data.get('label'),
                    public=galley_form.cleaned_data.get('public'),
                )
            except UnicodeDecodeError:
                messages.add_message(
                    request,
                    messages.ERROR,
                    _("Uploaded file is not UTF-8 encoded"),
                )
            except production_logic.ZippedGalleyError:
                messages.add_message(request, messages.ERROR,
                    "Galleys must be uploaded individually, not zipped",
                )

            if index == 0:
                if 'create_title_page' in request.POST:
                    if uploaded_file.content_type == 'application/pdf':
                        try:
                            core_logic.create_article_file_from_galley(article, request, galley)
                        except:
                            messages.add_message(
                                request,
                                messages.ERROR,
                                'Error creating tile page from pdf file.',
                            )
                    else:
                        messages.add_message(
                            request,
                            messages.WARNING,
                            'No pdf file. Cannot create title page.',
                        )
    else:
        messages.add_message(
            request,
            messages.WARNING,
            'Galley form not valid.',
        )

    if galley != None:
        context['galley']= serializers.serialize('json', [galley], fields=["article", "file", "label"])
    
    data = {
        'msg': loader.render_to_string('common/elements/messages.html', { 'messages': get_messages(request) }, None),
        'context': json.dumps(context)
    }
    return JsonResponse(data)

@GET_language_override
def handleSaveForm(request, article):
    with translation.override(request.override_language):
        article_form = submission_forms.ArticleInfo(request.POST, instance=article)

        if article_form.is_valid():
            article_form.save(request=request)

        pub_form = bc_forms.PublicationInfo(request.POST, instance=article)

        if pub_form.is_valid():
            pub_form.save()
            if article.primary_issue:
                article.primary_issue.articles.add(article)

            if article.date_published:
                article.stage = submission_models.STAGE_READY_FOR_PUBLICATION
                article.save()

        remote_form = bc_forms.RemoteArticle(request.POST, instance=article)

        if remote_form.is_valid():
            remote_form.save()

    return True


