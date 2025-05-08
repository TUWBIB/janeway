import traceback
import re
import json
import lxml.etree as etree
import datetime
import locale
from typing import List
from xml.sax.saxutils import escape, unescape

from django.conf import settings
from django.db.models import Max
from django.utils.timezone import get_current_timezone

from submission import models as submission_models
from journal import models as journal_models
from sync import models as sync_models
from identifiers import models as identifier_models
from sync.datacite import api as datacite_api
from laapy import API,MarcRecord,ControlField,DataField,SubField

def create_article_doi(article: submission_models.Article):
    doi: str

    api = datacite_api.API(json_str=json.dumps(settings.DATACITE))
    journal_code = article.journal.code
    journal_settings = settings.DATACITE['journals'][journal_code]
    # new method
    if "pattern_article" in journal_settings: 
        doi = journal_settings["pattern_article"]
        if "***publication_year***" in doi:
            doi = doi.replace("***publication_year***", article.issue.publication_year)
        if "***counter_within_issue***" in doi:
            dois_issue = identifier_models.Identifier.objects.filter(article__journal__issue=article.issue,id_type="doi")
            cnt = len(dois_issue) + 1
            doi = doi.replace("***counter_within_issue***",str(cnt))
    # legacy
    else:
        prefix = api.journals[journal_code]['prefix']
        namespace_separator = api.journals[journal_code]['namespace_separator']
        doi = prefix+'/'+namespace_separator+'.'+ article.primary_issue.publication_year + '.'+str(article.pk+int(api.options['id_offset']))

    return doi


def create_issue_doi(issue: journal_models.Issue):
    doi: str

    api = datacite_api.API(json_str=json.dumps(settings.DATACITE))
    journal_code = issue.journal.code
    journal_settings = settings.DATACITE['journals'][journal_code]
    # new method
    if "pattern_issue" in journal_settings: 
        doi = journal_settings["pattern_issue"]
        if "***publication_year***" in doi:
            doi = doi.replace("***publication_year***",str(issue.date.year))

    return doi


def checkArticleMandatoryFields(article):
    errors = []

    if article.primary_issue is None:
        errors.append("primary issue not set")

    if len(article.frozen_authors())==0:
        errors.append("no authors for article")
    
    return errors

def dataciteMetadata(article_id=None,issue_id=None):
    xml: str = ''
    errors: List[str] = []
    warnings: List[str] = []

    if article_id:
        article = submission_models.Article.objects.get(pk=article_id)
        api = datacite_api.API(json_str=json.dumps(settings.DATACITE))

        errors = checkArticleMandatoryFields(article)

        l = []

        if not errors:
            try:
                l.append('<resource xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns="http://datacite.org/schema/kernel-4" xsi:schemaLocation="http://datacite.org/schema/kernel-4 http://schema.datacite.org/meta/kernel-4/metadata.xsd">')
            
                doi = article.get_doi()
                if doi is None:
                    doi = create_article_doi(article)
                else:
                    if not api.doiConformsToCurrentConfiguration(article.journal.code,doi):
                        errors.append("existing DOI doesn't conform to current configuration")

                l.append('<identifier identifierType="DOI">')
                l.append(doi)
                l.append('</identifier>')

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
                    if author.author and author.author.orcid:
                        l.append('<nameIdentifier nameIdentifierScheme="ORCID" schemeURI="https://orcid.org">')
                        l.append(author.author.orcid)
                        l.append('</nameIdentifier>')
                    l.append('</creator>')
                l.append('</creators>')

                l.append('<titles>')
                if article.language is not None:
                    l.append('<title')
                    l.append(' xml:lang="')
                    l.append(article.language[0:2])
                    l.append('">')
                    l.append(escape(article.getTitleRAW))
                    l.append('</title>')
                else:
                    l.append('<title>')
                    l.append(escape(article.getTitleRAW))
                    l.append('</title>')
                    warnings.append("article language not set")

                if article.getSubTitleRAW:
                    if article.language is not None:
                        l.append('<title titleType="Subtitle"')
                        l.append(' xml:lang="')
                        l.append(article.language[0:2])
                        l.append('">')
                        l.append(escape(article.getSubTitleRAW))
                        l.append('</title>')
                    else:
                        l.append('<title>')
                        l.append(escape(article.getSubTitleRAW))
                        l.append('</title>')

                if article.language == 'eng':
                    if article.getTitleDE:
                        l.append('<title titleType="AlternativeTitle">')
                        l.append(escape(article.getTitleDE))
                        l.append('</title>')

                    if article.getSubTitleDE:
                        l.append('<title titleType="Other">')
                        l.append(escape(article.getSubTitleDE))
                        l.append('</title>')

                if article.language == 'deu':
                    if article.getTitleEN:
                        l.append('<title titleType="AlternativeTitle">')
                        l.append(escape(article.getTitleEN))
                        l.append('</title>')

                    if article.getSubTitleEN:
                        l.append('<title titleType="Other">')
                        l.append(escape(article.getSubTitleEN))
                        l.append('</title>')
                

                l.append('</titles>')

                if article.keywords:
                    l.append('<subjects>')
                    for kw in article.keywords.filter(language='en'):
                        l.append('<subject xml:lang="en">')
                        l.append(escape(kw.word))
                        l.append('</subject>')
                    for kw in article.keywords.filter(language='de'):
                        l.append('<subject xml:lang="de">')
                        l.append(escape(kw.word))
                        l.append('</subject>')
                    l.append('</subjects>')

                l.append('<publisher>')
                if article.journal.code == 'JFM':
                    l.append('Journal für Facility Management')
                elif article.journal.code == 'OES':
                    l.append('Der Öffentliche Sektor - The Public Sector')
                elif article.journal.code == 'ARW':
                    l.append(article.publisher)
                l.append('</publisher>')

                l.append('<publicationYear>')
                l.append(article.primary_issue.publication_year)
                l.append('</publicationYear>')

                l.append('<dates>')
                l.append('<date dateType="Issued">')
                l.append(article.primary_issue.publication_year)
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
                if article.getAbstractEN or article.getAbstractDE:
                    if article.getAbstractEN:
                        l.append('<description xml:lang="')
                        l.append('en" descriptionType="Abstract">')
                        l.append(escape(article.getAbstractEN))
                        l.append('</description>')
                    if article.getAbstractDE:
                        l.append('<description xml:lang="')
                        l.append('de" descriptionType="Abstract">')
                        l.append(escape(article.getAbstractDE))
                        l.append('</description>')
                else:
                    warnings.append("neither english nor german abstract")

                if article.journal.code == 'JFM':
                    pass
                elif article.journal.code == 'OES':
                    l.append('<description descriptionType="SeriesInformation">Der Öffentliche Sektor - The Public Sector ')
                    l.append(str(article.primary_issue.volume))
                    l.append('(')
                    if article.primary_issue.tuw_issue_str is not None:
                        l.append(article.primary_issue.tuw_issue_str)
                    else:
                        l.append(str(article.primary_issue.issue))
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

    elif issue_id:
        issue: journal_models.Issue = journal_models.Issue.objects.get(pk=issue_id)
        api = datacite_api.API(json_str=json.dumps(settings.DATACITE))

        l = []

        if not errors:
            try:
                l.append('<resource xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns="http://datacite.org/schema/kernel-4" xsi:schemaLocation="http://datacite.org/schema/kernel-4 http://schema.datacite.org/meta/kernel-4.6/metadata.xsd">')

                doi = issue.doi
                if not doi:
                    doi = create_issue_doi(issue)

                l.append('<identifier identifierType="DOI">')
                l.append(doi)
                l.append('</identifier>')

                l.append('<creators>')
                l.append('<creator>')
                l.append('<creatorName nameType="Personal">')
                l.append("Kubinger, Wilfried")
                l.append('</creatorName>')
                l.append('<givenName>')
                l.append('Wilfried')
                l.append('</givenName>')
                l.append('<familyName>')
                l.append('Kubinger')
                l.append('</familyName>')
                l.append('<nameIdentifier schemeURI="https://orcid.org/" nameIdentifierScheme="ORCID">')
                l.append('0000-0002-6965-7794')
                l.append('</nameIdentifier>')
                l.append('</creator>')

                l.append('<creator>')
                l.append('<creatorName nameType="Personal">')
                l.append("Kranzer, Simon")
                l.append('</creatorName>')
                l.append('<givenName>')
                l.append('Simon')
                l.append('</givenName>')
                l.append('<familyName>')
                l.append('Kranzer')
                l.append('</familyName>')
                l.append('<nameIdentifier schemeURI="https://orcid.org/" nameIdentifierScheme="ORCID">')
                l.append('0000-0002-5907-4624')
                l.append('</nameIdentifier>')
                l.append('</creator>')

                l.append('<creator>')
                l.append('<creatorName nameType="Personal">')
                l.append("Vincze, Markus")
                l.append('</creatorName>')
                l.append('<givenName>')
                l.append('Markus')
                l.append('</givenName>')
                l.append('<familyName>')
                l.append('Vincze')
                l.append('</familyName>')
                l.append('<nameIdentifier schemeURI="https://orcid.org/" nameIdentifierScheme="ORCID">')
                l.append('0000-0002-2799-491X')                         
                l.append('</nameIdentifier>')
                l.append('</creator>')

                l.append('</creators>')

                l.append('<titles>')
                l.append('<title>')
                l.append(escape(issue.issue_title))
                l.append('</title>')
                l.append('</titles>')                



                l.append('<publisher>')
                if issue.journal.code == 'ARW':
                    l.append('Gesellschaft für Messtechnik, Automatisierung und Robotik - GMAR und Automatisierungs- und Regelungstechnik Institut der TU Wien')
                l.append('</publisher>')

                l.append('<publicationYear>')
                l.append(str(issue.date.year))
                l.append('</publicationYear>')
#
#
#                if article.get_urn() is not None:
#                    l.append('<alternateIdentifiers>')
#                    l.append('<alternateIdentifier alternateIdentifierType="URN">')
#                    l.append(article.get_urn())
#                    l.append('</alternateIdentifier>')
#                    l.append('</alternateIdentifiers>')
#
#
#                if article.license is not None and article.license.short_name != 'Copyright':
#                    l.append('<rightsList>')
#                    l.append('<rights rightsURI="')
#                    l.append(article.license.url)
#                    l.append('" xml:lang="en-US">')
#                    l.append(article.license.name)
#                    l.append('</rights>')
#                    l.append('</rightsList>')
#
#                l.append('<resourceType resourceTypeGeneral="Text">Journal Article</resourceType>')
#
#                if article.journal.code == 'JFM':
#                    pass
#                elif article.journal.code == 'OES':
#                    l.append('<relatedIdentifiers>')
#                    l.append('<relatedIdentifier relatedIdentifierType="ISSN" relationType="IsPartOf">2412-3862</relatedIdentifier>')
#                    l.append('</relatedIdentifiers>')
#
#                l.append('<descriptions>')
#                if article.getAbstractEN or article.getAbstractDE:
#                    if article.getAbstractEN:
#                        l.append('<description xml:lang="')
#                        l.append('en" descriptionType="Abstract">')
#                        l.append(escape(article.getAbstractEN))
#                        l.append('</description>')
#                    if article.getAbstractDE:
#                        l.append('<description xml:lang="')
#                        l.append('de" descriptionType="Abstract">')
#                        l.append(escape(article.getAbstractDE))
#                        l.append('</description>')
#                else:
#                    warnings.append("neither english nor german abstract")
#
#                if article.journal.code == 'JFM':
#                    pass
#                elif article.journal.code == 'OES':
#                    l.append('<description descriptionType="SeriesInformation">Der Öffentliche Sektor - The Public Sector ')
#                    l.append(str(article.primary_issue.volume))
#                    l.append('(')
#                    if article.primary_issue.tuw_issue_str is not None:
#                        l.append(article.primary_issue.tuw_issue_str)
#                    else:
#                        l.append(str(article.primary_issue.issue))
#                    l.append('): ')
#                    l.append(str(article.page_numbers))
#                    l.append('</description>')
#                l.append('</descriptions>')



                l.append('<resourceType resourceTypeGeneral="ConferenceProceeding">')
                l.append("---to be 𝄞 determined---'")
                l.append('</resourceType>')
                l.append('</resource>')

                xml = ''.join(l)
                x = etree.fromstring(xml)
                xml = etree.tostring(x, 
                                     encoding='unicode',
                                     pretty_print=True)
                
                xml = '<?xml version="1.0" encoding="UTF-8"?>\n'+xml

            except Exception as e:
                print (traceback.format_exc())
                errors.append(''.join(['error creating xml: ',str(e)]))

    return (xml, errors, warnings)

def getCurrentDataCiteXML(article_id=None,issue_id=None):
    xml: str = ''
    warnings: List[str] = []
    errors: List[str] = []

    if article_id:
        article = submission_models.Article.objects.get(pk=article_id)
        api = datacite_api.API(json_str=json.dumps(settings.DATACITE))

        doi = article.get_doi()
        if doi is None:
            errors.append("No DOI registered")
        else:
            if not api.doiConformsToCurrentConfiguration(article.journal.code,doi):
                errors.append("existing DOI doesn't conform to current configuration")

        if not errors:
            status,content=api.getMetadata(doi)
            if status != 'success':
                errors.append(content)
            else:
                xml = content
    elif issue_id:
        issue = journal_models.Issue.objects.get(pk=issue_id)
        doi = issue.doi
        api = datacite_api.API(json_str=json.dumps(settings.DATACITE))
        if doi is None:
            errors.append("No DOI registered")
        if not errors:
            status,content = api.getMetadata(doi)
            if status != 'success':
                errors.append(content)
            else:
                xml = content

    return (xml, errors, warnings)

def getCurrentDataCiteURL(article_id=None,issue_id=None):
    url: str = ''
    warnings: List[str] = []
    errors: List[str] = []    

    if article_id:
        
        article = submission_models.Article.objects.get(pk=article_id)
        api = datacite_api.API(json_str=json.dumps(settings.DATACITE))

        doi = article.get_doi()
        if doi is None:
            errors.append("No DOI registered")
        else:
            if not api.doiConformsToCurrentConfiguration(article.journal.code,doi):
                errors.append("existing DOI doesn't conform to current configuration")

        if not errors:
            status,content=api.getURL(doi)
            if status != 'success':
                errors.append(content)
            else:
                url=content
    elif issue_id:
        issue = journal_models.Issue.objects.get(pk=issue_id)
        doi = issue.doi
        api = datacite_api.API(json_str=json.dumps(settings.DATACITE))
        if not errors:
            status,content=api.getURL(doi)
            if status != 'success':
                errors.append(content)
            else:
                url=content

    print (f"{url} {errors} {warnings}")

    return (url, errors, warnings)


def metadataUpdated(doi,article_id=None,issue_id=None):
    status = "success"
    errors: List[str] = []
    datacite_status: str = submission_models.DATACITE_STATE_NONE

    if article_id:
        try:
            article = submission_models.Article.objects.get(pk=article_id)
            if not article.datacite_state or article.datacite_state==submission_models.DATACITE_STATE_NONE:
                article.datacite_state = submission_models.DATACITE_STATE_DRAFT
            article.datacite_ts = datetime.datetime.now(get_current_timezone())
            article.save()
            if not article.get_doi():
                identifier_models.Identifier.objects.create(article=article,id_type='doi',identifier=doi)
            elif article.get_doi()!=doi:
                identifier_models.Identifier.objects.filter(article=article,id_type='doi',identifier=doi).delete()
                identifier_models.Identifier.objects.create(article=article,id_type='doi',identifier=doi)
            datacite_status = article.datacite_state
        except Exception as e:
            errors.append(''.join(['error writing db: ',str(e)]))
            status = "error"
        
    
    elif issue_id:
        try:
            issue = journal_models.Issue.objects.get(pk=issue_id)
            issue.doi = doi
            issue.save()
            datacite,_ = sync_models.DataCite.objects.get_or_create(issue=issue)
            datacite.ts = datetime.datetime.now(get_current_timezone())
            if not datacite.status or datacite.status == sync_models.DataCite.DATACITE_STATUS_NONE:
                datacite.status = sync_models.DataCite.DATACITE_STATUS_DRAFT
            datacite.save()
            datacite_status = datacite.status 
        except Exception as e:
            errors.append(''.join(['error writing db: ',str(e)]))
            status = "error"
        
        return (status,errors,datacite_status)            
   

def urlSet(doi,article_id=None,issue_id=None):
    status = "success"
    errors: List[str] = []    

    if article_id:
        try:
            article = submission_models.Article.objects.get(pk=article_id)
            if not article.datacite_state or article.datacite_state!=submission_models.DATACITE_STATE_FINDABLE:
                article.datacite_state = submission_models.DATACITE_STATE_FINDABLE
            article.datacite_ts = datetime.datetime.now(get_current_timezone())
            article.save()
        except Exception as e:
            errors.append(''.join(['error writing db: ',str(e)]))
            status = "error"
    elif issue_id:
        pass

    return (status,errors)

def doiDeleted(doi,article=None,issue=None):
    status = "success"
    errors: List[str] = []    

    if article:
        try:
            article = submission_models.Article.objects.get(pk=article.pk)
            article.datacite_state = submission_models.DATACITE_STATE_NONE
            article.datacite_ts = datetime.datetime.now(get_current_timezone())
            article.save()
            identifier_models.Identifier.objects.filter(article=article,id_type='doi',identifier=doi).delete()
        except Exception as e:
            print (traceback.format_exc())
            errors.append(''.join(['error writing db: ',str(e)]))
            status = "error"
    elif issue:
        try:
            issue = journal_models.Issue.objects.get(pk=issue.pk)
            issue.doi = None
            issue.save()
            datacite = sync_models.DataCite.objects.get(issue=issue)
            if datacite:
                datacite.delete()
        except Exception as e:
            print (traceback.format_exc())
            errors.append(''.join(['error writing db: ',str(e)]))
            status = "error"

    return (status,errors)


def checkArticleMarcMandatoryFields(article):
    errors = []

    if article.get_doi() is None:
        errors.append("doi not set")
    
    return errors


def articleToMarc(article):
    errors = checkArticleMarcMandatoryFields(article)
    warnings = []
    xml = ''
    l = []

    if not errors:
        try:
            source_parallel_title = ''

            lang=article.language
            if lang=='deu':
                lang = 'ger'

            mr=MarcRecord()
            mr.leader="03012naa a2200373 c 4500"
            mr.addControlField(ControlField.createControlField("007","cr#|||||||||||"))

            now = datetime.datetime.now()
            s = ''
            s += now.strftime('%y%m%d')
            s += '|'
            s += article.primary_issue.publication_year
            s += '    |||     o     ||| 0 '

            if lang:
                s += lang    
            else:
                s += '   '

            s += ' c'
            mr.addControlField(ControlField.createControlField("008",s))


            # 024 7_ doi, urn
            if article.get_doi():
                datafield=DataField.createDataField("024","7"," ")
                datafield.addSubField(SubField.createSubField("a",article.get_doi()))
                datafield.addSubField(SubField.createSubField("2","doi"))
                mr.addDataField(datafield)
            if article.get_urn():
                datafield=DataField.createDataField("024","7"," ")
                datafield.addSubField(SubField.createSubField("a",article.get_urn()))
                datafield.addSubField(SubField.createSubField("2","urn"))
                mr.addDataField(datafield)

            # 040 __ kat inst
            datafield=DataField.createDataField("040"," "," ")
            datafield.addSubField(SubField.createSubField("a","TUW"))
            datafield.addSubField(SubField.createSubField("b","ger"))
            datafield.addSubField(SubField.createSubField("c","JW"))
            datafield.addSubField(SubField.createSubField("d","AT-UBTUW"))
            datafield.addSubField(SubField.createSubField("e","rda"))
            mr.addDataField(datafield)

            # 041 __ language
            if lang:
                datafield=DataField.createDataField("041"," "," ")
                datafield.addSubField(SubField.createSubField("a",lang))
                mr.addDataField(datafield)

            # 044 __ country code, fix
            datafield=DataField.createDataField("044"," "," ")
            datafield.addSubField(SubField.createSubField("a",'XA-AT'))
            mr.addDataField(datafield)

            # primary author
            author=article.frozen_authors()[0]  
            if author:
                datafield=DataField.createDataField("100","1"," ")
                datafield.addSubField(SubField.createSubField("a",''.join([author.last_name,', ',author.first_name])))
                datafield.addSubField(SubField.createSubField("4",'aut'))
                if author.is_correspondence_author:
                    datafield.addSubField(SubField.createSubField("4",'oth'))
                    datafield.addSubField(SubField.createSubField("e",'Corresponding author'))
                mr.addDataField(datafield)
                if author.author.gndid:
                    datafield.addSubField(SubField.createSubField("0",'(DE-588)'+author.author.gndid))


            # 245 10 title statement
            # primary language from raw field, then if
            # article language == 'deu', use english title / subtitle for subfield b
            # article language == 'eng', use german title / subtitle for subfield b
            author=article.frozen_authors()[0]  
            if author:
                datafield=DataField.createDataField("245","1","0")
            else:
                datafield=DataField.createDataField("245","0","0")
            datafield.addSubField(SubField.createSubField("a",escape(article.getTitleRAW)))
            sf_b = ''
            if article.subtitle:
                sf_b += article.getSubTitleRAW

            if article.language == 'deu':
                if article.getTitleEN:
                    source_parallel_title = 'en'
                    sf_b += ' = '+article.getTitleEN

                if article.getSubTitleEN:
                    sf_b += ' : '+article.getSubTitleEN

            elif article.language == 'eng':
                if article.getTitleDE:
                    source_parallel_title = 'de'
                    sf_b += ' = '+article.getTitleDE
                if article.getSubTitleDE:
                    sf_b += ' : '+article.getSubTitleDE
           
            if sf_b:
                datafield.addSubField(SubField.createSubField("b",escape(sf_b)))

            auth = []
            for author in article.frozen_authors():
                auth.append(author.first_name+" "+author.last_name)
            datafield.addSubField(SubField.createSubField("c",", ".join(auth)))
            mr.addDataField(datafield)

            # 246 11
            if source_parallel_title == 'de':
                if article.getTitleDE:
                    datafield=DataField.createDataField("246","1","1")
                    datafield.addSubField(SubField.createSubField("a",escape(article.getTitleDE)))
                    if article.getSubTitleDE:
                        datafield.addSubField(SubField.createSubField("b",escape(article.getSubTitleDE)))
                    mr.addDataField(datafield)
            elif source_parallel_title == 'en':
                if article.getTitleEN:
                    datafield=DataField.createDataField("246","1","1")
                    datafield.addSubField(SubField.createSubField("a",escape(article.getTitleEN)))
                    if article.getSubTitleEN:
                        datafield.addSubField(SubField.createSubField("b",escape(article.getSubTitleEN)))
                    mr.addDataField(datafield)

            # 251 __ coar
            datafield=DataField.createDataField("251"," "," ")
            datafield.addSubField(SubField.createSubField("a","vor"))
            datafield.addSubField(SubField.createSubField("2","coar"))
            mr.addDataField(datafield)

            # 264 _1 publication
            datafield=DataField.createDataField("264"," ","1")
            datafield.addSubField(SubField.createSubField("a","Wien"))
            datafield.addSubField(SubField.createSubField("b","Technische Universität Wien"))
            datafield.addSubField(SubField.createSubField("c",article.primary_issue.publication_year))
            mr.addDataField(datafield)

            # 300 __ physical description
            datafield=DataField.createDataField("300"," "," ")
            match=re.match(r'(\d+)-(\d+)',article.page_numbers)
            no_pages=None
            if match:
                first_page=int(match[1])
                last_page=int(match[2])
                no_pages=last_page-first_page+1
            sf_a="Online-Ressource"
            if no_pages:
                if no_pages == 1:
                    sf_a+=" ("+str(no_pages)+" Seite)"
                else:
                    sf_a+=" ("+str(no_pages)+" Seiten)"
            datafield.addSubField(SubField.createSubField("a",sf_a))
            datafield.addSubField(SubField.createSubField("b","Illustrationen, Diagramme"))
            mr.addDataField(datafield)
           
            # 336-338
            datafield=DataField.createDataField("336"," "," ")
            datafield.addSubField(SubField.createSubField("b","txt"))
            mr.addDataField(datafield)

            datafield=DataField.createDataField("337"," "," ")
            datafield.addSubField(SubField.createSubField("b","c"))
            mr.addDataField(datafield)

            datafield=DataField.createDataField("338"," "," ")
            datafield.addSubField(SubField.createSubField("b","cr"))
            mr.addDataField(datafield)

            # 347 __ digital file
            datafield=DataField.createDataField("347"," "," ")
            datafield.addSubField(SubField.createSubField("a","Textdatei"))
            datafield.addSubField(SubField.createSubField("b","PDF"))
            mr.addDataField(datafield)

            # 500 __ peer reviewed
            if article.peer_reviewed:
                datafield=DataField.createDataField("500"," "," ")
                datafield.addSubField(SubField.createSubField("a","Refereed/Peer-reviewed"))
                mr.addDataField(datafield)

            # 506 0_, open access, fixed
            datafield=DataField.createDataField("506","0"," ")
            datafield.addSubField(SubField.createSubField("a","Open Access"))
            datafield.addSubField(SubField.createSubField("f","Unrestricted online access"))
            datafield.addSubField(SubField.createSubField("2","star"))
            mr.addDataField(datafield)

            # 520, abstracts
            if article.getAbstractEN:
                datafield=DataField.createDataField("520"," "," ")
                datafield.addSubField(SubField.createSubField("a","eng:"+" "+escape(article.getAbstractEN)))
                mr.addDataField(datafield)

            if article.getAbstractDE:
                datafield=DataField.createDataField("520"," "," ")
                datafield.addSubField(SubField.createSubField("a","ger:"+" "+escape(article.getAbstractDE)))
                mr.addDataField(datafield)

            # 540, Lizenz
            if article.license is not None and article.license.short_name != 'Copyright':
                datafield=DataField.createDataField("540"," "," ")
                datafield.addSubField(SubField.createSubField("f",article.license.short_name))
                datafield.addSubField(SubField.createSubField("2","cc"))
                datafield.addSubField(SubField.createSubField("u",article.license.url))
                mr.addDataField(datafield)

            # 700 further authors
            if article.frozen_authors() and len(article.frozen_authors())>1:
                for author in article.frozen_authors()[1:]:
                    datafield=DataField.createDataField("700","1"," ")
                    datafield.addSubField(SubField.createSubField("a",''.join([author.last_name,', ',author.first_name])))
                    datafield.addSubField(SubField.createSubField("4",'aut'))
                    if author.is_correspondence_author:
                        datafield.addSubField(SubField.createSubField("4",'oth'))
                        datafield.addSubField(SubField.createSubField("e",'Corresponding author'))
                    mr.addDataField(datafield)
                    if author.author.gndid:
                        datafield.addSubField(SubField.createSubField("0",'(DE-588)'+author.author.gndid))

            # 773 08 relation
            datafield=DataField.createDataField("773","0","8")
            datafield.addSubField(SubField.createSubField("i","Enthalten in"))
            if article.journal.code == 'OES':
                datafield.addSubField(SubField.createSubField("t","Der Öffentliche Sektor - The Public Sector"))
            elif article.journal.code == 'JFM':            
                datafield.addSubField(SubField.createSubField("t","IFM Journal"))
            else:
                pass
            datafield.addSubField(SubField.createSubField("d",article.primary_issue.publication_year))
            if article.journal.code == 'OES':
                s = 'Jahrgang '+str(article.primary_issue.volume)+' ('+ article.primary_issue.publication_year + '), '
                s += 'Heft '+str(article.primary_issue.tuw_issue_str if article.primary_issue.tuw_issue_str else article.primary_issue.issue)+', '
                s += 'Seiten '+article.page_numbers
                datafield.addSubField(SubField.createSubField("g",s))
            elif article.journal.code == 'JFM':
                s = 'Jahrgang ('+ article.primary_issue.publication_year + '), '
                s += 'Heft '+str(article.primary_issue.tuw_issue_str if article.primary_issue.tuw_issue_str else article.primary_issue.issue)+', '
                s += 'Seiten '+article.page_numbers
                datafield.addSubField(SubField.createSubField("g",s))
            else:
                pass
            if article.journal.code == 'OES':
                datafield.addSubField(SubField.createSubField("w","(AT-OBV)AC10863779"))
            elif article.journal.code == 'JFM':
                datafield.addSubField(SubField.createSubField("w","(AT-OBV)AC13348910"))
            else:
                pass
            mr.addDataField(datafield)            

            # 856 link, doi
            if article.get_doi():
                datafield=DataField.createDataField("856","4","0")
                datafield.addSubField(SubField.createSubField("q",'text/html'))
                datafield.addSubField(SubField.createSubField("u",'https://doi.org/'+article.get_doi()))
                datafield.addSubField(SubField.createSubField("x",'TUW'))
                datafield.addSubField(SubField.createSubField("z",'kostenfrei'))
                datafield.addSubField(SubField.createSubField("3",'Volltext'))
                mr.addDataField(datafield)

            # 970 2_
            datafield=DataField.createDataField("970","2"," ")
            datafield.addSubField(SubField.createSubField("a",'TUW'))
            datafield.addSubField(SubField.createSubField("d",'OA-ARTICLE'))
            mr.addDataField(datafield)

            # 971 8_ keywords_de
            if article.keywords:
                kws = []
                for k in article.keywords.filter(language='de'):
                    kws.append(str(k))
                s = ' / '.join(kws)
                if s:
                    datafield=DataField.createDataField("971","8"," ")
                    datafield.addSubField(SubField.createSubField("a",s))
                    mr.addDataField(datafield)

            # 971 9_keywords en
            if article.keywords:
                kws = []
                for k in article.keywords.filter(language='en'):
                    kws.append(str(k))
                s = ' / '.join(kws)
                if s:
                    datafield=DataField.createDataField("971","9"," ")
                    datafield.addSubField(SubField.createSubField("a",s))
                    mr.addDataField(datafield)

            # 996 33 reposiTUm
            datafield=DataField.createDataField("996","3","3")
            datafield.addSubField(SubField.createSubField("9",'LOCAL'))
            datafield.addSubField(SubField.createSubField("a",'Gold Open Access ; Journal Hosting System'))
            mr.addDataField(datafield)

            xml = mr.toXML()

            x = etree.fromstring(xml)
            xml = etree.tostring(x, pretty_print=True).decode("utf-8")
            xml = '<?xml version="1.0" encoding="UTF-8"?>\n'+xml

        except Exception as e:
            print (traceback.format_exc())
            errors.append(''.join(['error creating xml: ',str(e)]))

    return (xml, errors, warnings)


def setMMSId(article,mmsid):
    errs = []
    try:
        identifier_models.Identifier.objects.filter(article=article,id_type='mmsid').delete()
        identifier_models.Identifier.objects.create(article=article,id_type='mmsid',identifier=mmsid)
    except Exception as e:
        print (traceback.format_exc())
        errs.append(''.join(['error writing db: ',str(e)]))

    return errs

def setAC(article,ac):
    errs = []
    try:
        identifier_models.Identifier.objects.filter(article=article,id_type='ac').delete()
        identifier_models.Identifier.objects.create(article=article,id_type='ac',identifier=ac)
    except Exception as e:
        print (traceback.format_exc())
        errs.append(''.join(['error writing db: ',str(e)]))

    return errs


#def get_next_doi(journal_code,year):
#    api = datacite_api.API(json_str=json.dumps(settings.DATACITE))
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
