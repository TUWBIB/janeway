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


# Create your views here.

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

        modal = None

        if request.POST:
            if 'add_author' in request.POST:
                return handleAddAuthor(request, article)
            
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
        'modal': modal,
        'additional_fields': additional_fields,
        'galley_form': galley_form
    }

    return render(request, template, context)

@editor_user_required
def backcontent_delete_article(request, article_id):
    article = get_object_or_404(submission_models.Article, pk=article_id, journal=request.journal)
    article.delete()
    messages.add_message(request, messages.SUCCESS, '%s deleted', article_id)
    return redirect(reverse('backcontent'))

@editor_user_required
def backcontent_order_authors(request, article_id):
    article = get_object_or_404(submission_models.Article, pk=article_id)
    author_pks = [int(pk) for pk in request.POST.getlist('authors[]')]
    for author in article.authors.all():
        order = author_pks.index(author.pk)
        author_order, c = submission_models.ArticleAuthorOrder.objects.get_or_create(
            article=article,
            author=author,
            defaults={'order': order}
        )

        if not c:
            author_order.order = order
            author_order.save()

    article.snapshot_authors()

    return HttpResponse('Complete')


@editor_user_required
def backcontent_delete_author(request, article_id, author_id):
    """Allows submitting author to delete an author object."""
    article = get_object_or_404(
        submission_models.Article,
        pk=article_id,
        journal=request.journal
    )
    author = get_object_or_404(
        core_models.Account,
        pk=author_id
    )

    article.authors.remove(author)

    if article.correspondence_author == author:
        article.correspondence_author = None
        article.save()

    try:
        ordering = submission_models.ArticleAuthorOrder.objects.get(
            article=article,
            author=author,
        ).delete()
    except submission_models.ArticleAuthorOrder.DoesNotExist:
        pass

    try:
        ordering = submission_models.FrozenAuthor.objects.get(
            article=article,
            author=author,
        ).delete()
    except submission_models.FrozenAuthor.DoesNotExist:
        print("frozen author does not exists")
        pass
       
    return redirect(reverse('backcontent_article', kwargs={'article_id': article_id}))

@editor_user_required
def backcontent_add_author(request,article_id):
    s=request.POST.get("search","")
    message="unknown"
    status="info"
    author = None

    # check email or orcid or gndid
    authors=core_models.Account.objects.filter(email=s) | core_models.Account.objects.filter(orcid=s) | core_models.Account.objects.filter(gndid=s)
    if authors:
        if authors.count()>1:
            message="multiple authors found, something's very fishy"
            status="error"
        else:
            author=authors[0]
    else:
        l = s.split(' ')
        if len(l)==1:
            authors = core_models.Account.objects.filter(last_name__istartswith=l[0].lower())
        else:
            authors = core_models.Account.objects.filter(last_name__istartswith=l[0].lower()) & core_models.Account.objects.filter(first_name__istartswith=l[1].lower())

        if authors:
            if authors.count()>1:
                message="sorry, multiple authors found"
                status="error"
            else:
                author = authors[0]
         

    if author:
        article=submission_models.Article.objects.filter(id=article_id)[0]

        #check if account already has author role for this journal
        role=core_models.Role.objects.filter(name='author')[0]
        accountroles=core_models.AccountRole.objects.filter(user=author,journal=request.journal,role=role)
        if accountroles:
            pass
        else:
            author.add_account_role(role_slug='author', journal=request.journal)

        #check if author already added to article
        found=False

        for a in article.authors.all():
            if a.id==author.id:
                found=True

        if not found:
            article.authors.add(author)
            aao=setAuthorOrder(article,author)
            submission_models.ArticleAuthorOrder.objects.get_or_create(article=article, author=author)
            article.snapshot_authors()

            message="author added"
            status="success"
            context = { 
                'url': reverse('backcontent_delete_author', kwargs={'article_id': article.pk, 'author_id': author.pk }), 
                'aao': serializers.serialize('json', [aao], fields=["pk","order"]),  
                'author' : serializers.serialize('json',[aao.author], fields=["pk","last_name","first_name","email"]) 
            }
        else:
            message="author already set"
            status="warning"
    else:
        message="no author found for "+s
        status="warning"

    if status=="success": 
        response = JsonResponse({'status': status,'message':message,
                'context': json.dumps(context)})
    else:
        response= JsonResponse({'status': status,'message':message})


    return response

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


def handleAddAuthor(request, article):
    author_form = bc_forms.BackContentAuthorForm(request.POST)
    modal = 'author'
    context = { }


    author_exists = submission_logic.check_author_exists(request.POST.get('email'))
    if author_exists:
        author_on_article = article.authors.filter(id=author_exists.id)

        if not author_on_article:
            article.authors.add(author_exists)
            aao=setAuthorOrder(article,author_exists)
            article.snapshot_authors()

            messages.add_message(request, messages.SUCCESS, '%s added to the article' % author_exists.full_name())
            context = { 
                    'url': reverse('backcontent_delete_author', kwargs={'article_id': article.pk, 'author_id': author_exists.pk }), 
                    'aao': serializers.serialize('json', [aao], fields=["pk","order"]),  
                    'author' : serializers.serialize('json',[author_exists], fields=["pk","last_name","first_name","email"]) 
            }
        else:
            messages.add_message(request, messages.ERROR, '%s is already author' % author_exists.full_name())
    else:
        if author_form.is_valid():
            if author_form.cleaned_data["first_name"] and author_form.cleaned_data["last_name"]:
                new_author = author_form.save(commit=False)
                new_author.username = new_author.email
                new_author.set_password(shared.generate_password())
                new_author.save()
                new_author.add_account_role(role_slug='author', journal=request.journal)

                article.authors.add(new_author)
                aao=setAuthorOrder(article,new_author)
                article.snapshot_authors()
                
                messages.add_message(request, messages.SUCCESS, '%s added to the article' % new_author.full_name())
                context = { 
                    'url': reverse('backcontent_delete_author', kwargs={'article_id': article.pk, 'author_id': new_author.pk }), 
                    'aao': serializers.serialize('json', [aao], fields=["pk","order"]),  
                    'author' : serializers.serialize('json',[new_author], fields=["pk","last_name","first_name","email"]) 
                }
            else:
                messages.add_message(request, messages.ERROR, '%s could not be found. Enter Firstname and Lastname' % request.POST.get('email'))
        else:
            messages.add_message(request, messages.ERROR,'% form invalid') 
            print (author_form.errors)

    data = {
        'msg': loader.render_to_string('common/elements/messages.html', { 'messages': get_messages(request) }, None),
        'context': json.dumps(context)
    }
    return JsonResponse(data)

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

        correspondence_author = request.POST.get('main-author', None)

        if correspondence_author:
            author = core_models.Account.objects.get(pk=correspondence_author)
            article.correspondence_author = author
            article.save()

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

def setAuthorOrder(article,author):
    order=article.next_author_sort() 
    aao=submission_models.ArticleAuthorOrder()
    aao.article=article
    aao.author=author
    aao.order=order
    aao.save()
    return aao

