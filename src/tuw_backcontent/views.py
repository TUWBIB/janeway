import json

from django.shortcuts import render
from django.conf import settings
from django.contrib import messages
from django.contrib.messages import get_messages
from django.core import serializers
from django.urls import reverse
from django.http import Http404, HttpResponse, JsonResponse
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
        author_form = bc_forms.BackContentAuthorForm()
        pub_form = bc_forms.PublicationInfo(instance=article)
        remote_form = bc_forms.RemoteArticle(instance=article)
        galley_form = production_forms.GalleyForm()
        new_author_form = submission_forms.EditFrozenAuthor()

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
        'form': author_form,
        'pub_form': pub_form,
        'galleys': prod_logic.get_all_galleys(article),
        'remote_form': remote_form,
        'additional_fields': additional_fields,
        'galley_form': galley_form,
        'authors': submission_logic.get_current_authors(article, request),
        "new_author_form": new_author_form,
    }

    return render(request, template, context)

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


