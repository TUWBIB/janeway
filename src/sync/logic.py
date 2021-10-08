import traceback
import re
import lxml.etree as etree
import datetime
import locale
from xml.sax.saxutils import escape, unescape

from django.db.models import Max
from django.utils.timezone import get_current_timezone

from submission import models as submission_models
from identifiers import models as identifier_models
from sync.datacite import api as datacite_api
from laapy import API,MarcRecord,ControlField,DataField,SubField

def create_article_doi(article):
    api = datacite_api.API()
    journal_code = article.journal.code
    prefix = api.journals[journal_code]['prefix']
    namespace_separator = api.journals[journal_code]['namespace_separator']
    doi = prefix+'/'+namespace_separator+'.'+str(article.primary_issue.tuw_year)+'.'+str(article.pk+int(api.options['id_offset']))

    return doi

def checkArticleMandatoryFields(article):
    errors = []

    if article.primary_issue is None:
        errors.append("primary issue not set")

    if len(article.frozen_authors())==0:
        errors.append("no authors for article")
    
    return errors

def articleToDataCiteXML(article_id):
    article = submission_models.Article.objects.get(pk=article_id)
    api = datacite_api.API()

    errors = checkArticleMandatoryFields(article)

    warnings = []
    xml = ''
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
                l.append(escape(article.title))
                l.append('</title>')
            else:
                l.append('<title>')
                l.append(escape(article.title))
                l.append('</title>')
                warnings.append("article language not set")

            if article.subtitle:
                if article.language is not None:
                    l.append('<title titleType="Subtitle"')
                    l.append(' xml:lang="')
                    l.append(article.language[0:2])
                    l.append('">')
                    l.append(escape(article.subtitle))
                    l.append('</title>')
                else:
                    l.append('<title>')
                    l.append(escape(article.subtitle))
                    l.append('</title>')

            if article.title_de:
                l.append('<title titleType="AlternativeTitle">')
                l.append(escape(article.title_de))
                l.append('</title>')

            if article.subtitle_de:
                l.append('<title titleType="Other">')
                l.append(escape(article.subtitle_de))
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
            if article.journal.code == 'JFM' or article.journal.code == 'JFMT':
                l.append('Journal für Facility Management')
            elif article.journal.code == 'OES' or article.journal.code == 'OEST':
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

            if article.journal.code == 'JFM' or article.journal.code == 'JFMT':
                pass
            elif article.journal.code == 'OES' or article.journal.code == 'OEST':
                l.append('<relatedIdentifiers>')
                l.append('<relatedIdentifier relatedIdentifierType="ISSN" relationType="IsPartOf">2412-3862</relatedIdentifier>')
                l.append('</relatedIdentifiers>')

            l.append('<descriptions>')
            if article.abstract or article.abstract_de:
                if article.abstract:
                    l.append('<description xml:lang="')
                    l.append('en" descriptionType="Abstract">')
                    l.append(escape(article.abstract))
                    l.append('</description>')
                if article.abstract_de:
                    l.append('<description xml:lang="')
                    l.append('de" descriptionType="Abstract">')
                    l.append(escape(article.abstract_de))
                    l.append('</description>')
            else:
                warnings.append("neither english nor german abstract")

            if article.journal.code == 'JFM' or article.journal.code == 'JFMT':
                pass
            elif article.journal.code == 'OES' or article.journal.code == 'OEST':
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

    return (xml, errors, warnings)

def getCurrentDataCiteXML(article_id):
    article = submission_models.Article.objects.get(pk=article_id)
    api = datacite_api.API()

    warnings = []
    errors = []
    xml = ''

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
            xml=content

    return (xml, errors, warnings)

def getCurrentDataCiteURL(article_id):
    article = submission_models.Article.objects.get(pk=article_id)
    api = datacite_api.API()

    warnings = []
    errors = []
    url = ''

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

    return (url, errors, warnings)


def metadataUpdated(article_id,doi):
    status = "success"
    errors = []
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
    except Exception as e:
        errors.append(''.join(['error writing db: ',str(e)]))
        status = "error"

    return (status,errors,article.datacite_state)

def urlSet(article_id,doi):
    status = "success"
    errors = []
    try:
        article = submission_models.Article.objects.get(pk=article_id)
        if not article.datacite_state or article.datacite_state!=submission_models.DATACITE_STATE_FINDABLE:
            article.datacite_state = submission_models.DATACITE_STATE_FINDABLE
        article.datacite_ts = datetime.datetime.now(get_current_timezone())
        article.save()
    except Exception as e:
        errors.append(''.join(['error writing db: ',str(e)]))
        status = "error"

    return (status,errors)

def doiDeleted(article_id,doi):
    status = "success"
    errors = []
    try:
        article = submission_models.Article.objects.get(pk=article_id)
        article.datacite_state = submission_models.DATACITE_STATE_NONE
        article.datacite_ts = datetime.datetime.now(get_current_timezone())
        article.save()
        identifier_models.Identifier.objects.filter(article=article,id_type='doi',identifier=doi).delete()
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
            s += str(article.primary_issue.tuw_year)
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

            # 245 10 title statement
            author=article.frozen_authors()[0]  
            if author:
                datafield=DataField.createDataField("245","1","0")
            else:
                datafield=DataField.createDataField("245","0","0")
            datafield.addSubField(SubField.createSubField("a",escape(article.title)))
            sf_b = ''
            if article.subtitle:
                sf_b += article.subtitle
            if article.title_de:
                sf_b += ' = '+article.title_de
            if article.subtitle_de:
                sf_b += ' : '+article.subtitle_de
            if sf_b:
                datafield.addSubField(SubField.createSubField("b",escape(sf_b)))

            auth = []
            for author in article.frozen_authors():
                auth.append(author.first_name+" "+author.last_name)
            datafield.addSubField(SubField.createSubField("c",", ".join(auth)))
            mr.addDataField(datafield)

            # 246 11
            if article.title_de:
                datafield=DataField.createDataField("246","1","1")
                datafield.addSubField(SubField.createSubField("a",escape(article.title_de)))
                if article.subtitle_de:
                    datafield.addSubField(SubField.createSubField("b",escape(article.subtitle_de)))
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
            datafield.addSubField(SubField.createSubField("c",str(article.primary_issue.tuw_year)))
            mr.addDataField(datafield)


            # 300 __ physical description
            datafield=DataField.createDataField("300"," "," ")
            match=re.match('(\d+)-(\d+)',article.page_numbers)
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
            if article.abstract:
                datafield=DataField.createDataField("520"," "," ")
                datafield.addSubField(SubField.createSubField("a","eng:"+" "+escape(article.abstract)))
                mr.addDataField(datafield)

            if article.abstract_de:
                datafield=DataField.createDataField("520"," "," ")
                datafield.addSubField(SubField.createSubField("a","ger:"+" "+escape(article.abstract_de)))
                mr.addDataField(datafield)

            # 542, Lizenz
            if article.license is not None and article.license.short_name != 'Copyright':
                datafield=DataField.createDataField("542"," "," ")
                datafield.addSubField(SubField.createSubField("a","Unter einer CC-Lizenz, Details siehe Link"))
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

            # 773 08 relation
            datafield=DataField.createDataField("773","0","8")
            datafield.addSubField(SubField.createSubField("i","Enthalten in"))
            if article.journal.code == 'OES' or article.journal.code == 'OEST':
                datafield.addSubField(SubField.createSubField("t","Der Öffentliche Sektor - The Public Sector"))
            elif article.journal.code == 'JFM' or article.journal.code == 'JFM':            
                datafield.addSubField(SubField.createSubField("t","IFM Journal"))
            else:
                pass
            datafield.addSubField(SubField.createSubField("d",str(article.primary_issue.tuw_year)))
            if article.journal.code == 'OES' or article.journal.code == 'OEST':
                s = 'Jahrgang '+str(article.primary_issue.volume)+' ('+str(article.primary_issue.tuw_year)+'), '
                s += 'Heft '+str(article.primary_issue.tuw_issue_str if article.primary_issue.tuw_issue_str else article.primary_issue.issue)+', '
                s += 'Seiten '+article.page_numbers
                datafield.addSubField(SubField.createSubField("g",s))
            elif article.journal.code == 'JFM' or article.journal.code == 'JFMT':
                s = 'Jahrgang ('+str(article.primary_issue.tuw_year)+'), '
                s += 'Heft '+str(article.primary_issue.tuw_issue_str if article.primary_issue.tuw_issue_str else article.primary_issue.issue)+', '
                s += 'Seiten '+article.page_numbers
                datafield.addSubField(SubField.createSubField("g",s))
            else:
                pass
            if article.journal.code == 'OES' or article.journal.code == 'OEST':
                datafield.addSubField(SubField.createSubField("w","(AT-OBV)AC10863779"))
            elif article.journal.code == 'JFM' or article.journal.code == 'JFM':
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
#    api = datacite_api.API()
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
