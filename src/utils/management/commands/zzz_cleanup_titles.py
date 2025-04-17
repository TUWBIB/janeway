from io import BytesIO

from django.core.management.base import BaseCommand
from django.utils.translation import activate
from django.utils import translation
from django.conf import settings
from django.db import connection, transaction

from submission import models as submission_models

import xlsxwriter

class Command(BaseCommand):
    """A management command to add missing default settings to journals."""

    help = "Adds missing default settings to journals."

    def add_arguments(self, parser):
        """ Adds arguments to Django's management command-line parser.

        :param parser: the parser to which the required arguments will be added
        :return: None
        """
        parser.add_argument('--dryrun', default=True)
        parser.add_argument('--fileout', default=None)
        parser.add_argument('--mode', default='tsa')
        parser.add_argument('--minpk', default=1)
        parser.add_argument('--maxpk', default=99999)

    def handle(self, *args, **options):
        article: submission_models.Article

        sql_abstract = """
        UPDATE 
        submission_article 
        SET 
        abstract = %s, abstract_en = %s, abstract_de = %s, abstract_de_tuw = %s
        WHERE id = %s
        """

        sql_title = """
        UPDATE 
        submission_article 
        SET 
        title = %s, title_en = %s, title_de = %s, title_de_tuw = %s
        WHERE id = %s
        """

        sql_subtitle = """
        UPDATE 
        submission_article 
        SET 
        subtitle = %s, subtitle_en = %s, subtitle_de = %s, subtitle_de_tuw = %s
        WHERE id = %s
        """


        dryrun = options.get('dryrun', True)
        if type(dryrun) == str and dryrun.lower() == 'false': dryrun = False
        fileout = options.get('fileout', 'result.xlsx')
        minpk = options.get('minpk', 1)
        maxpk = options.get('maxpk', 99999)
        mode = options.get('mode', None)

        abstract_exceptions_no_changes = [698]
        abstract_exceptions_delete_abstract_de = [111,118,119,137,569]
        abstract_exceptions_delete_abstract_en = []

        output = BytesIO()

        wb = xlsxwriter.Workbook(output)
        format_top = wb.add_format()
        format_top.set_align('top')
        format_top.set_align('left')

        format_wrap = wb.add_format()
        format_wrap.set_align('top')
        format_top.set_align('left')
        format_wrap.set_text_wrap()

        sheet = wb.add_worksheet('before')
        sheet.freeze_panes(1, 0)

        row = 0
        col = iter(range(0,30))
        sheet.write(row,next(col),'journal',format_top)
        sheet.write(row,next(col),'id',format_top)
        sheet.write(row,next(col),'language',format_top)
        if 't' in mode:
            sheet.write(row,next(col),'title',format_top)
            sheet.write(row,next(col),'title_en',format_top)
            sheet.write(row,next(col),'title_de',format_top)
            sheet.write(row,next(col),'title_de_tuw',format_top)
        if 's' in mode:
            sheet.write(row,next(col),'subtitle',format_top)
            sheet.write(row,next(col),'subtitle_en',format_top)
            sheet.write(row,next(col),'subtitle_de',format_top)
            sheet.write(row,next(col),'subtitle_de_tuw',format_top)
        if 'a' in mode:
            sheet.write(row,next(col),'abstract',format_top)
            sheet.write(row,next(col),'abstract_en',format_top)
            sheet.write(row,next(col),'abstract_de',format_top)
            sheet.write(row,next(col),'abstract_de_tuw',format_top)
        sheet.write(row,next(col),'action')

        articles = submission_models.Article.objects.filter(pk__gte=minpk,pk__lte=maxpk).order_by('id')

        l_title_is_english_delete_german =  [
            #jfm
            113,120,126,133,139,
            #oes
            185,204,419,434,435,436,444,446,447,458,460,461,472
        ]

        l_title_is_german_delete_english =  [
            # jfm
            1,2,3,10,11,12,19,20,21,27,28,29,36,37,38,43,44,45,50,51,52,57,58,59,64,65,66,71,72,73,79,80,81,86,87,88,93,94,95,100,101,102,107,108,109,114,115,
            121,122,127,128,134,135,140,141,
            # oes
            145,146,147,155,156,161,162,167,168,169,171,172,173,178,179,186,187,188,194,195,196,197,
            205,206,211,212,213,214,215,217,218,219,224,225,226,231,232,233,234,235,237,238,239,243,
            244,245,246,249,250,251,252,253,256,257,258,263,264,265,270,271,272,273,274,279,280,281,
            286,287,288,289,295,296,297,298,303,304,305,310,318,319,320,321,322,326,327,328,329,330,
            334,335,336,337,346,347,348,349,350,355,356,357,358,362,363,364,365,369,370,371,379,380,
            381,382,383,384,389,390,391,392,403,404,405,406,420,421,422,429,432,433,445,457,459,473,
            474,475,486,487,488,489,490,506,507,508,509,510,520,521,522,523,539
        ]

        for article in articles:
            print (f"processing article {article.pk}")

            l = []
            title_changed = False
            subtitle_changed = False
            abstract_changed = False

            title = article.getTitleRAW
            title_en = article.getTitleEN
            title_de = article.getTitleDE
            title_de_tuw = getattr(article,'title_de_tuw','')
            subtitle = article.getSubTitleRAW
            subtitle_en = article.getSubTitleEN
            subtitle_de = article.getSubTitleDE
            subtitle_de_tuw = getattr(article,'subtitle_de_tuw','')
            abstract = article.getAbstractRAW
            abstract_en = article.getAbstractEN
            abstract_de = article.getAbstractDE
            abstract_de_tuw = getattr(article,'abstract_de_tuw','')

            language = article.language
            if language is None: language = ''

            row += 1 
            col = iter(range(0,30))
            sheet.write(row,next(col),article.journal.code,format_top)
            sheet.write(row,next(col),article.pk,format_top)
            sheet.write(row,next(col),language,format_top)
            if 't' in mode:
                sheet.write(row,next(col),title,format_wrap)
                sheet.write(row,next(col),title_en,format_wrap)
                sheet.write(row,next(col),title_de,format_wrap)
                sheet.write(row,next(col),title_de_tuw,format_wrap)
            if 's' in mode:
                sheet.write(row,next(col),subtitle,format_wrap)
                sheet.write(row,next(col),subtitle_en,format_wrap)
                sheet.write(row,next(col),subtitle_de,format_wrap)
                sheet.write(row,next(col),subtitle_de_tuw,format_wrap)
            if 'a' in mode:
                sheet.write(row,next(col),abstract,format_wrap)
                sheet.write(row,next(col),abstract_en,format_wrap)
                sheet.write(row,next(col),abstract_de,format_wrap)
                sheet.write(row,next(col),abstract_de_tuw,format_wrap)

            ## title corrections
            if 't' in mode:
                # hardcoded cases
                if article.pk in l_title_is_german_delete_english and title_en:
                    l.append('delete english title')                        
                    article.__dict__['title_en'] = None
                    title_changed = True

                elif article.pk in l_title_is_english_delete_german and title_de:
                    l.append('delete german title')                        
                    article.__dict__['title_de'] = None
                    title_changed = True


                # no parallel title
                # article language german
                # english title set
                # german title set
                # >> move title from english to german
                elif language == 'deu' and title and title_en and not title_de and not title_de_tuw:
                    l.append('move title from english to german')
                    article.__dict__['title_de'] = title_en
                    article.__dict__['title_en'] = None
                    title_changed = True

                # no parallel title
                # article language english
                # english title not set
                # german title set
                # >> move title from german to english
                elif language == 'eng' and title and title_de and not title_en and not title_de_tuw:
                    l.append('move title from german to english')
                    article.__dict__['title_en'] = title_de
                    article.__dict__['title_de'] = None
                    title_changed = True


                # no parallel title
                # article language german
                # english title set
                # german title set
                # german and english title equal
                # >> delete english title
                elif language == 'deu' and title and title_en and title_de and not title_de_tuw and (title_en.strip() == title_de.strip()):
                    l.append('delete english title')
                    article.__dict__['title_en'] = None
                    title_changed = True


                # no parallel title
                # article language english
                # english title set
                # german title set
                # german and english title equal
                # >> delete german title
                elif language == 'eng' and title and title_en and title_de and not title_de_tuw and (title_en.strip() == title_de.strip()):
                    l.append('delete german title')
                    article.__dict__['title_de'] = None
                    title_changed = True

                # parallel title set
                # article language germen
                # >> delete parallel title, set title to german title, set parallel_title as english 
                elif language == 'deu' and title and title_en and title_de and title_de_tuw:
                    l.append('set german title as main title, set parallel title as english title, delete parallel title')
                    title = title_de
                    article.__dict__['title_en'] = title_de_tuw
                    article.title_de_tuw = None
                    title_changed = True

            ### subtitle corrections
            if 's' in mode:
                # no parallel subtitle
                # article language english
                # subtitle set
                # english subtitle not set
                # german subtitle not set
                # >> populate english subtitle
                if language == 'eng' and subtitle and not subtitle_en and not subtitle_de and not subtitle_de_tuw:
                    l.append('populate english subtitle')
                    article.__dict__['subtitle_en'] = subtitle
                    subtitle_changed = True

                # no parallel subtitle
                # article language german
                # subtitle set
                # english subtitle not set
                # german subtitle not set
                # >> populate german subtitle
                elif language == 'deu' and subtitle and not subtitle_en and not subtitle_de and not subtitle_de_tuw:
                    l.append('populate german subtitle')
                    article.__dict__['subtitle_de'] = subtitle
                    subtitle_changed = True

                # no parallel subtitle
                # article language german
                # subtitle set
                # english subtitle not set
                # german subtitle not set
                # >> populate german subtitle
                elif language == 'deu' and subtitle and not subtitle_en and not subtitle_de and not subtitle_de_tuw:
                    l.append('populate german subtitle')
                    article.__dict__['subtitle_de'] = subtitle
                    subtitle_changed = True

                # article language german
                # subtitle set
                # parallel subtitle set
                # english subtitle not set
                # german subtitle not set
                # >> populate german subtitle from title, move parallel title to english subtitle, delete parallel subtitle
                elif language == 'deu' and subtitle and not subtitle_en and not subtitle_de and subtitle_de_tuw:
                    l.append('populate german subtitle from title, move parallel title to english subtitle')
                    article.__dict__['subtitle_de'] = subtitle
                    article.__dict__['subtitle_en'] = subtitle_de_tuw
                    article.subtitle_de_tuw = None
                    subtitle_changed = True

            ### abstract corrections:
            if 'a' in mode:
                # exceptions - no action
                if article.pk in abstract_exceptions_no_changes:
                    pass

                # exception
                # delete abstract_de
                # article language german, only abstract is english
                elif article.pk in abstract_exceptions_delete_abstract_de and abstract_de:
                    l.append('delete abstract_de, hardcoded')
                    article.__dict__['abstract_de'] = None
                    abstract_changed = True


                # no "parallel abstract"
                # article language german
                # english abstract set
                # >> delete english abstract
                elif language == 'deu' and abstract and abstract_en and abstract_de and not abstract_de_tuw and abstract_en.strip() == abstract_de.strip():
                    l.append('delete english abstract')
                    article.__dict__['abstract_en'] = None
                    abstract_changed = True

                # no "parallel abstract"
                # article language english
                # german abstract set
                # >> delete german abstract
                elif language == 'eng' and abstract and abstract_en and abstract_de and not abstract_de_tuw and abstract_en.strip() == abstract_de.strip():
                    l.append('delete german abstract')
                    article.__dict__['abstract_de'] = None
                    abstract_changed = True

                # no "parallel abstract"
                # article language english
                # german abstract set
                # >> move german abstract to english
                elif language == 'eng' and abstract and not abstract_en and abstract_de and not abstract_de_tuw:
                    l.append('move german abstract to english')
                    article.__dict__['abstract_de'] = None
                    article.__dict__['abstract_en'] = abstract_de
                    abstract_changed = True                    

                # language german
                # no abstract
                # no english absract
                # only abstract_de_tuw_set
                # >> delete abstract_de_tuw, set abstract raw and german
                elif language == 'deu' and not abstract and not abstract_de and not abstract_en and abstract_de_tuw:
                    l.append('move abstract_de_tuw to abstract and abstract_de')
                    article.abstract_de_tuw = None
                    article.abstract = abstract_de_tuw
                    article.__dict__['abstract_en'] = None
                    article.__dict__['abstract_de'] = abstract_de_tuw
                    abstract_changed = True

                # language german
                # everything set
                # >> make primary abstract german, set abstract_de, delete abstract_de_tuw
                elif language == 'deu' and abstract and abstract_de and abstract_en and abstract_de_tuw:
                    l.append('move abstract_de_tuw to abstract and abstract_de')
                    article.abstract_de_tuw = None
                    article.abstract = abstract_de_tuw
                    article.__dict__['abstract_de'] = abstract_de_tuw
                    article.__dict__['abstract_en'] = abstract_en
                    abstract_changed = True

            sheet.write(row,next(col),'; '.join(l),format_top)

            if l:
                print("; ".join(l))

            if not dryrun and l:
                with connection.cursor() as cur:
                    if 'a' in mode and abstract_changed:
                        cur.execute(sql_abstract,
                                    [article.getAbstractRAW, article.getAbstractEN, article.getAbstractDE,article.abstract_de_tuw,
                                     str(article.pk)]
                                    )
                        print (f"updating abstract")
                        

                    if 't' in mode and title_changed:
                        cur.execute(sql_title,
                                    [article.getTitleRAW, article.getTitleEN, article.getTitleDE, article.title_de_tuw,
                                     str(article.pk)]
                                    )
                        print (f"updating title")


                    if 's' in mode and subtitle_changed:
                        cur.execute(sql_subtitle,
                                    [article.getSubTitleRAW, article.getSubTitleEN, article.getSubTitleDE, article.subtitle_de_tuw,
                                     str(article.pk)]
                                    )
                        print (f"updating subtitle")

        if not dryrun:
            articles = submission_models.Article.objects.filter(pk__gte=minpk,pk__lte=maxpk).order_by('id')

        sheet = wb.add_worksheet('after')
        sheet.freeze_panes(1, 0)
        row = 0
        col = iter(range(0,30))
        sheet.write(row,next(col),'journal',format_top)
        sheet.write(row,next(col),'id',format_top)
        sheet.write(row,next(col),'language',format_top)
        if 't' in mode:
            sheet.write(row,next(col),'title',format_top)
            sheet.write(row,next(col),'title_en',format_top)
            sheet.write(row,next(col),'title_de',format_top)
            sheet.write(row,next(col),'title_de_tuw',format_top)
        if 's' in mode:
            sheet.write(row,next(col),'subtitle',format_top)
            sheet.write(row,next(col),'subtitle_en',format_top)
            sheet.write(row,next(col),'subtitle_de',format_top)
            sheet.write(row,next(col),'subtitle_de_tuw',format_top)
        if 'a' in mode:
            sheet.write(row,next(col),'abstract',format_top)
            sheet.write(row,next(col),'abstract_en',format_top)
            sheet.write(row,next(col),'abstract_de',format_top)
            sheet.write(row,next(col),'abstract_de_tuw',format_top)

        for article in articles:
            title = article.getTitleRAW
            title_en = article.getTitleEN
            title_de = article.getTitleDE
            title_de_tuw = getattr(article,'title_de_tuw','')
            subtitle = article.getSubTitleRAW
            subtitle_en = article.getSubTitleEN
            subtitle_de = article.getSubTitleDE
            subtitle_de_tuw = getattr(article,'subtitle_de_tuw','')
            abstract = article.getAbstractRAW
            abstract_en = article.getAbstractEN
            abstract_de = article.getAbstractDE
            abstract_de_tuw = getattr(article,'abstract_de_tuw','')

            language = article.language
            if language is None: language = ''

            row += 1 
            col = iter(range(0,30))
            sheet.write(row,next(col),article.journal.code,format_top)
            sheet.write(row,next(col),article.pk,format_top)
            sheet.write(row,next(col),language,format_top)
            if 't' in mode:
                sheet.write(row,next(col),title,format_wrap)
                sheet.write(row,next(col),title_en,format_wrap)
                sheet.write(row,next(col),title_de,format_wrap)
                sheet.write(row,next(col),title_de_tuw,format_wrap)
            if 's' in mode:
                sheet.write(row,next(col),subtitle,format_wrap)
                sheet.write(row,next(col),subtitle_en,format_wrap)
                sheet.write(row,next(col),subtitle_de,format_wrap)
                sheet.write(row,next(col),subtitle_de_tuw,format_wrap)
            if 'a' in mode:
                sheet.write(row,next(col),abstract,format_wrap)
                sheet.write(row,next(col),abstract_en,format_wrap)
                sheet.write(row,next(col),abstract_de,format_wrap)
                sheet.write(row,next(col),abstract_de_tuw,format_wrap)

        wb.close()


        if fileout:
            output.seek(0)
            with open(fileout, "wb") as f:
               f.write(output.read())
    
