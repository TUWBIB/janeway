import traceback
import re
import lxml.etree as etree
import datetime

from django.db.models import Max
from django.utils.timezone import get_current_timezone

from submission import models as submission_models
from identifiers import models as identifier_models
from sync.datacite import api as datacite_api

def create_article_doi(article):
    api = datacite_api.API.getInstance()
    journal_code = article.journal.code
    prefix = api.journals[journal_code]['prefix']
    namespace_separator = api.journals[journal_code]['namespace_separator']
    doi = prefix+'/'+namespace_separator+'.'+str(article.primary_issue.tuw_year)+'.'+str(article.pk+int(api.options['id_offset']))

    return doi


def article_to_DataCiteXML(article_id):
    article = submission_models.Article.objects.get(pk=article_id)
    api = datacite_api.API.getInstance()

    warnings = []
    errors = []
    xml = ''
    l = []

    try:
        l.append('<resource xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns="http://datacite.org/schema/kernel-4" xsi:schemaLocation="http://datacite.org/schema/kernel-4 http://schema.datacite.org/meta/kernel-4/metadata.xsd">')

        if article.primary_issue is None:
            raise ValueError("primary issue not set")

        doi = article.get_doi()
        if doi is None:
            doi = create_article_doi(article)
        else:
            if not api.doiConformsToCurrentConfiguration(article.journal.code,doi):
                errors.append("existing DOI doesn't conform to current configuration")


        l.append('<identifier identifierType="DOI">')
        l.append(doi)
        l.append('</identifier>')

        if len(article.frozen_authors())>0:
            l.append('<creators>')
            for author in article.frozen_authors():
                l.append('<creator>')
                l.append('<creatorName nameType="Personal">')
                l.append(''.join([author.last_name,', ',author.first_name]))
                l.append('</creatorName>')
                l.append('<givenName>')
                l.append(author.first_name)
                l.append('</givenName>')
                l.append('<familyName>')
                l.append(author.last_name)
                l.append('</familyName>')
                l.append('</creator>')
            l.append('</creators>')
        else:
            warnings.append("no authors for article")

        l.append('<titles>')
        if article.language is not None:
            l.append('<title')
            l.append(' xml:lang="')
            l.append(article.language[0:2])
            l.append('">')
            l.append(article.title)
            l.append('</title>')
        else:
            l.append('<title>')
            l.append(article.title)
            l.append('</title>')
            warnings.append("article language not set")

        if article.subtitle:
            if article.language is not None:
                l.append('<title titleType="Subtitle"')
                l.append(' xml:lang="')
                l.append(article.language[0:2])
                l.append('">')
                l.append(article.subtitle)
                l.append('</title>')
            else:
                l.append('<title>')
                l.append(article.subtitle)
                l.append('</title>')

        if article.title_de:
            l.append('<title titleType="AlternativeTitle">')
            l.append(article.title_de)
            l.append('</title>')

        if article.subtitle_de:
            l.append('<title titleType="Other">')
            l.append(article.subtitle_de)
            l.append('</title>')

        l.append('</titles>')


        l.append('<publisher>')
        if article.journal.code == 'JFM':
            l.append('Journal für Facility Management')
        elif article.journal.code == 'OES':
            l.append('Der Öffentliche Sektor - The Public Sector')
        l.append('</publisher>')

        l.append('<publicationYear>')
        l.append(str(article.primary_issue.tuw_year))
        l.append('</publicationYear>')

        l.append('<dates>')
        l.append('<date dateType="Issued">')
        l.append(str(article.primary_issue.tuw_year))
        l.append('</date>')
        l.append('</dates>')

        if article.get_urn() is not None:
            l.append('<alternateIdentifiers>')
            l.append('<alternateIdentifier alternateIdentifierType="URN">')
            l.append(article.get_urn())
            l.append('</alternateIdentifier>')
            l.append('</alternateIdentifiers>')


        if article.license is not None and article.license.short_name != 'Copyright':
            l.append('<rightsList>')
            l.append('<rights rightsURI="')
            l.append(article.license.url)
            l.append('" xml:lang="en-US">')
            l.append(article.license.name)
            l.append('</rights>')
            l.append('</rightsList>')

        l.append('<resourceType resourceTypeGeneral="Text">Journal Article</resourceType>')

        if article.journal.code == 'JFM':
            pass
        elif article.journal.code == 'OES':
            l.append('<relatedIdentifiers>')
            l.append('<relatedIdentifier relatedIdentifierType="ISSN" relationType="IsPartOf">2412-3862</relatedIdentifier>')
            l.append('</relatedIdentifiers>')

        l.append('<descriptions>')
        if article.abstract or article.abstract_de:
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
        else:
            warnings.append("neither english nor german abstract")

        if article.journal.code == 'JFM':
            pass
        elif article.journal.code == 'OES':
            l.append('<description descriptionType="SeriesInformation">Der Öffentliche Sektor - The Public Sector ')
            l.append(str(article.primary_issue.volume))
            l.append('(')
            l.append(article.primary_issue.tuw_issue_str)
            l.append('): ')
            l.append(str(article.page_numbers))
            l.append('</description>')
        l.append('</descriptions>')
        l.append('</resource>')

        xml = ''.join(l)

        x = etree.fromstring(xml)
        xml = etree.tostring(x, pretty_print=True).decode("utf-8")
        xml = '<?xml version="1.0" encoding="UTF-8"?>\n'+xml

    except Exception as e:
        print (traceback.format_exc())
        errors.append(''.join(['error creating xml: ',str(e)]))

    return (xml, errors, warnings)

def metadataUpdated(article_id,doi):
    status = "success"
    errors = []
    try:
        article = submission_models.Article.objects.get(pk=article_id)
        if not article.datacite_state or article.datacite_state==submission_models.DATACITE_STATE_DRAFT:
            article.datacite_state = submission_models.DATACITE_STATE_DRAFT
        article.datacite_ts = datetime.datetime.now(get_current_timezone())
        article.save()
        if not article.get_doi():
            identifier_models.Identifier.objects.create(article=article,id_type='doi',identifier=doi)
        elif article.get_doi()!=doi:
            identifier_models.Identifier.objects.filter(article=article,id_type='doi',identifier=doi).delete()
            identifier_models.Identifier.objects.create(article=article,id_type='doi',identifier=doi)
    except Exception as e:
        errors.append(''.join(['error writing db: ',str(e)]))
        status = "error"

    return (status,errors)

def urlSet(article_id,doi):
    status = "success"
    errors = []
    try:
        article = submission_models.Article.objects.get(pk=article_id)
        if not article.datacite_state or article.datacite_state==submission_models.DATACITE_STATE_FINDABLE:
            article.datacite_state = submission_models.DATACITE_STATE_FINDABLE
        article.datacite_ts = datetime.datetime.now(get_current_timezone())
        article.save()
    except Exception as e:
        errors.append(''.join(['error writing db: ',str(e)]))
        status = "error"

    return (status,errors)



#def get_next_doi(journal_code,year):
#    api = datacite_api.API.getInstance()
#    prefix = api.journals[journal_code]['prefix']
#    namespace_separator = api.journals[journal_code]['namespace_separator']
#    searchstr = prefix+'/'+namespace_separator
#    objects = identifier_models.Identifier.objects.filter(id_type='doi',identifier__startswith=searchstr)
#    max_use = objects.aggregate(Max('identifier'))['identifier__max']
#    max_use = max_use[len(searchstr):]
#    match = re.match('\d+\.(\d+)',max_use)
#    max_use = match[1]
#    max_use = int(max_use)+1
#    api_start = int(api.journals[journal_code]['start'])
#    next_suffix = max([max_use, api_start])
#    doi = searchstr+str(year)+'.'+str(next_suffix)
#
#    return doi

