import json
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


logger = get_logger(__name__)

## sync

@has_journal
@editor_user_required
def sync(request):
    articles = submission_models.Article.objects.filter(journal=request.journal)

    print ("cp0")


    if request.method  == "POST":
        if request.is_ajax():
            print ("ajax")

        print ("cp1")

        data=json.loads(request.body)
        article_id = data['article_id']
        operation = data["operation"]
        print (article_id)
        print (operation)

        if operation == "alma_down":
            pass
        elif operation == "alma_up":
            pass
        elif operation == "datacite_down":
            pass
        elif operation == "datacite_up":
            pass


        message = article_to_DataCiteXML(article_id)
        status="success"

        response = JsonResponse({'status': status,'message':message })

        return response

    template = 'journal/manage/sync/sync_articles.html'
    context = {
        'articles': articles,
    }

    return render(request, template, context)

@has_journal
@editor_user_required
def sync_article(request, article_id):
    logger.info("here")
    logger.info(request.method)
    if request.method == "POST":
        logger.debug("post")
        action=request.POST['action']
        logger.debug(action)

    return redirect(reverse('sync'))


@has_journal
@editor_user_required
def sync_article_alma_down(request, article_id):
    return redirect(reverse('sync'))

@has_journal
@editor_user_required
def sync_article_alma_up(request, article_id):
    return redirect(reverse('sync'))

@has_journal
@editor_user_required
def sync_article_datacite_down(request, article_id):
    return redirect(reverse('sync'))

@has_journal
@editor_user_required
def sync_article_datacite_up(request, article_id):
    return redirect(reverse('sync'))


def article_to_DataCiteXML(article_id):
    article = submission_models.Article.objects.get(pk=article_id)
    
    l = []
#    l.append('<?xml version="1.0" encoding="UTF-8"?>')
    l.append('<resource xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns="http://datacite.org/schema/kernel-4" xsi:schemaLocation="http://datacite.org/schema/kernel-4 http://schema.datacite.org/meta/kernel-4/metadata.xsd">')

    if article.frozen_authors:
        l.append('<creators>')
        for author in article.frozen_authors():
            l.append('<creatorName nameType="Personal">')
            l.append(author.full_name())
            l.append('</creatorName>')
            l.append('<givenName>')
            l.append(author.first_name)
            l.append('</givenName>')
            l.append('<familyName>')
            l.append(author.last_name)
            l.append('</familyName>')
        l.append('</creators>')

    l.append('<titles>')
    l.append('<title')
    l.append(' xml:lang="')
    l.append(article.language[0:2])
    l.append('">')
    l.append(article.title)
    l.append('</title>')

    # todo subtitle
    # todo alternative title, language ?
    # todo subtitle of alternative title ??
    l.append('</titles>')


    l.append('<publisher>')
    l.append('</publisher>')

    l.append('<publicationYear>')
    l.append('</publicationYear>')

    l.append('<dates>')
    l.append('<date dateType="Issued">')
#    l.append(article.date_published)
    l.append('</date>')
    l.append('</dates>')

    l.append('<resourceType resourceTypeGeneral="Text">Journal Article</resourceType>')

    if article.abstract or article.abstract_de:
        l.append('<descriptions>')
        if article.abstract:
            l.append('<description xml:lang="')
            l.append('en" descriptionType="Abstract">')
            l.append(article.abstract)
            l.append('</description>')
        if article.abstract_de:
            l.append('<description xml:lang="')
            l.append('de" descriptionType="Abstract">')
            l.append(article.abstract_de)
            l.append('</description>')
        l.append('</descriptions>')
    l.append('</resource>')

    xml = ''.join(l)

    print (xml)

    x = etree.fromstring(xml)
    xml = etree.tostring(x, pretty_print=True).decode("utf-8")

    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'+xml

    print (xml)

    return xml



#<?xml version="1.0" encoding="UTF-8"?>
#<resource xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns="http://datacite.org/schema/kernel-4" xsi:schemaLocation="http://datacite.org/schema/kernel-4 http://schema.datacite.org/meta/kernel-4/metadata.xsd">
#  <identifier identifierType="DOI">10.34749/JFM.2008.1516</identifier>
#  <creators>
#    <creator>
#      <creatorName nameType="Personal">Redlein, Alexander</creatorName>
#      <givenName>Alexander</givenName>
#      <familyName>Redlein</familyName>
#    </creator>
#    <creator>
#      <creatorName nameType="Personal">Pichlmüller, Horst</creatorName>
#      <givenName>Horst</givenName>
#      <familyName>Pichlmüller</familyName>
#    </creator>
#  </creators>
#  <titles>
#    <title xml:lang="de">Wirtschaftlichkeit von Facilities Management, Rechnet sich Facilities Management?</title>
#  </titles>
#  <publisher>Journal für Facility Management</publisher>
#  <publicationYear>2008</publicationYear>
#  <resourceType resourceTypeGeneral="Text">Journal Article</resourceType>
#  <dates>
#    <date dateType="Issued">2008</date>
#  </dates>
#  <version/>
#  <descriptions>
#    <description xml:lang="de" descriptionType="Abstract">Durch zunehmenden Wettbewerb und damit einhergehendem Kostendruck sowie einem sich rasch ändernden Arbeitsumfeld im Allgemeinen, und im Facility Management im Speziellen, ergibt sich die Notwendigkeit nach neuen Wegen für Synergien und Kosteneinsparungen zu suchen. Darüber hinaus nehmen sowohl der Komplexitätsgrad der Facilities aber auch die Gesetzlichen- und die Kundenanforderungen zu. Derzeit ist die Nutzung von Synergien zwischen den einzelnen Facility Services sehr gering. Eine Möglichkeit, um oben angeführte Anforderungen zu erfüllen, ist der „Integrated Facility Services“ (IFS) Ansatz. Dieser, auf Business Process Reengineering und Value Engineering basierende Ansatz, setzt sich aus zwei Schritten zusammen: 1.Optimierung der internen (Management)Prozesse (Facility Management) 2.Optimierung der operativen Leistungserbringung (Facility Services) Im zweiten Schritt werden mit methodischen Ansätzen die möglichen Synergien zwischen den einzelnen Servicesilos wie haustechnische Dienstleistungen, Security, Catering, Reinigung etc. untersucht. Durch die Nutzung der Synergien ergibt sich ein verbessertes Verhältnis von Kosten zu Output.
#</description>
#  </descriptions>
#</resource>