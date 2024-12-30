
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
        parser.add_argument('--pk', default=None)
        parser.add_argument('--mode', default='tsa')

    def handle(self, *args, **options):
        """Checks existing journal settings, adds missing ones.

        :param args: None
        :param options: None
        :return: None
        """
        dryrun = options.get('dryrun', True)
        fileout = options.get('fileout', 'result.xlsx')
        pk = options.get('pk', None)
        mode = options.get('mode', None)

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

        if pk is None:
            articles = submission_models.Article.objects.all().order_by('id')
        else:
            articles = submission_models.Article.objects.filter(pk=pk).order_by('id')

        count = 0
        for article in articles:
            l = []
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

            ## title corrections
            if 't' in mode:

                # no parallel title
                # article language german
                # english title set
                # >> delete english title
                if language == 'deu' and title and title_en and title_de and not title_de_tuw:
                    l.append('delete english title')
                    article.__dict__['title_en'] = None

                # no parallel title
                # article language english
                # german title set
                # >> delete german title
                if language == 'eng' and title and title_en and title_de and not title_de_tuw:
                    l.append('delete german title')
                    article.__dict__['title_de'] = None

                # parallel title set
                # article language germen
                # >> delete parallel title, set title to german title, set english title to parallel title
                if language == 'deu' and title and title_en and title_de and title_de_tuw:
                    l.append('set german title as main title, set english title to parallel title, delete parallel title')
                    article.title_de_tuw = None
                    with translation.override('en'):
                        article.title = title_de_tuw 
                    with translation.override('de'):
                        article.title = title_de

            ### subtitle corrections
            if 's' in mode:
                pass

            ### abstract corrections:
            if 'a' in mode:
                # no "parallel abstract"
                # article language german
                # english abstract set
                # >> delete english abstract
                if language == 'deu' and abstract and abstract_en and abstract_de and not abstract_de_tuw:
                    l.append('delete english abstract')
                    article.__dict__['abstract_en'] = None

                # no "parallel abstract"
                # article language english
                # german abstract set
                # >> delete german abstract
                if language == 'eng' and abstract and abstract_en and abstract_de and not abstract_de_tuw:
                    l.append('delete german abstract')
                    article.__dict__['abstract_de'] = None
                
                # language german, no abstract, no englisch absract, only abstract_de_tuw_set:
                # >> delete abstract_de_tuw, set abstract raw and german
                if language == 'deu' and not abstract and not abstract_de and not abstract_en and abstract_de_tuw:
                    l.append('move abstract from abstract_de_tuw')
                    article.abstract_de_tuw = None
                    with translation.override('de'):
                        article.abstract = abstract_de_tuw
                
                # language german
                # everything set
                # >> make primary abstract german, set abstract_de, delete abstract_de_tuw
                if language == 'deu' and abstract and abstract_de and abstract_en and abstract_de_tuw:
                    l.append('move abstract from abstract_de_tuw to abstract_de, make primary_abstract german')
                    article.abstract_de_tuw = None
                    with translation.override('de'):
                        article.abstract = abstract_de_tuw

            if not dryrun and l:
                article.save()

            row += 1 
            col = iter(range(0,30))
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
            sheet.write(row,next(col),'; '.join(l),format_top)

        sheet = wb.add_worksheet('after')
        sheet.freeze_panes(1, 0)

        row = 0
        col = iter(range(0,30))
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
    
