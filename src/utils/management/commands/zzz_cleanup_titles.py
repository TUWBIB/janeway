
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
        parser.add_argument('--fileout', default='result.xlsx')
        parser.add_argument('--mode', default='tsa')
        parser.add_argument('--minpk', default='tsa')
        parser.add_argument('--maxpk', default='tsa')

    def handle(self, *args, **options):
        """Checks existing journal settings, adds missing ones.

        :param args: None
        :param options: None
        :return: None
        """

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
        subsitle = %s, subtitle_en = %s, subtitle_de = %s, subtitle_de_tuw = %s
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

        wb = xlsxwriter.Workbook(fileout)
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

        l_title_is_german_delete_english =  [
            1,2,3
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
            title_de_tuw = article.title_de_tuw if article.title_de_tuw else ''
            subtitle = article.getSubTitleRAW
            subtitle_en = article.getSubTitleEN
            subtitle_de = article.getSubTitleDE
            subtitle_de_tuw = article.subtitle_de_tuw if article.subtitle_de_tuw else ''
            abstract = article.getAbstractRAW
            abstract_en = article.getAbstractEN
            abstract_de = article.getAbstractDE
            abstract_de_tuw = article.abstract_de_tuw if article.abstract_de_tuw else ''

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
                if not language:
                    if article.pk in l_title_is_german_delete_english and title_en:
                        l.append('delete english title')                        
                        article.__dict__['title_en'] = None
                        title_changed = True
                
                # no parallel title
                # article language german
                # english title set
                # >> delete english title
                elif language == 'deu' and title and title_en and title_de and not title_de_tuw:
                    l.append('delete english title')
                    article.__dict__['title_en'] = None
                    title_changed = True

                # no parallel title
                # article language english
                # german title set
                # >> delete german title
                elif language == 'eng' and title and title_en and title_de and not title_de_tuw:
                    l.append('delete german title')
                    article.__dict__['title_de'] = None
                    title_changed = True

                # parallel title set
                # article language germen
                # >> delete parallel title, set title to german title, set english title to parallel title
                elif language == 'deu' and title and title_en and title_de and title_de_tuw:
                    l.append('set german title as main title, set english title to parallel title, delete parallel title')
                    article.title_de_tuw = None
                    with translation.override('en'):
                        article.title = title_de_tuw 
                    with translation.override('de'):
                        article.title = title_de
                    title_changed = True

            ### subtitle corrections
            if 's' in mode:
                pass

            ### abstract corrections:
            if 'a' in mode:
                # exceptions - no action
                if article.pk in abstract_exceptions_no_changes:
                    l.append('in exception list, no changes')

                # exception
                # delete abstract_de
                # article language german, only abstract is english
                if article.pk in abstract_exceptions_delete_abstract_de:
                    l.append('delete abstract_de')
                    article.__dict__['abstract_de'] = None
                    abstract_changed = True


                # no "parallel abstract"
                # article language german
                # english abstract set
                # >> delete english abstract
                elif language == 'deu' and abstract and abstract_en and abstract_de and not abstract_de_tuw:
                    l.append('delete abstract_en')
                    article.__dict__['abstract_en'] = None
                    abstract_changed = True

                # no "parallel abstract"
                # article language english
                # german abstract set
                # >> delete german abstract
                elif language == 'eng' and abstract and abstract_en and abstract_de and not abstract_de_tuw:
                    l.append('delete abstract_de')
                    article.__dict__['abstract_de'] = None
                    abstract_changed = True

                # no "parallel abstract"
                # article language english
                # german abstract set
                # >> delete german abstract
                elif language == 'eng' and abstract and not abstract_en and abstract_de and not abstract_de_tuw:
                    l.append('move abstract_de to abstract_en')
                    article.__dict__['abstract_de'] = None
                    article.__dict__['abstract_en'] = abstract_de
                    abstract_changed = True                    

                # language german, no abstract, no englisch absract, only abstract_de_tuw_set:
                # >> delete abstract_de_tuw, set abstract raw and german
                elif language == 'deu' and not abstract and not abstract_de and not abstract_en and abstract_de_tuw:
                    l.append('move abstract_de_tuw to abstract and abstract_de')
                    article.abstract_de_tuw = None
                    article.__dict__['abstract'] = abstract_de_tuw
                    article.__dict__['abstract_en'] = ''
                    article.__dict__['abstract_de'] = abstract_de_tuw
                    abstract_changed = True

                # language german
                # everything set
                # >> make primary abstract german, set abstract_de, delete abstract_de_tuw
                elif language == 'deu' and abstract and abstract_de and abstract_en and abstract_de_tuw:
                    l.append('move abstract_de_tuw to abstract and abstract_de')
                    article.abstract_de_tuw = None
                    article.__dict__['abstract'] = abstract_de_tuw
                    article.__dict__['abstract_en'] = ''
                    abstract_changed = True

            sheet.write(row,next(col),'; '.join(l),format_top)


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
            title_de_tuw = article.title_de_tuw if article.title_de_tuw else ''
            subtitle = article.getSubTitleRAW
            subtitle_en = article.getSubTitleEN
            subtitle_de = article.getSubTitleDE
            subtitle_de_tuw = article.subtitle_de_tuw if article.subtitle_de_tuw else ''
            abstract = article.getAbstractRAW
            abstract_en = article.getAbstractEN
            abstract_de = article.getAbstractDE
            abstract_de_tuw = article.abstract_de_tuw if article.abstract_de_tuw else ''

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
    
