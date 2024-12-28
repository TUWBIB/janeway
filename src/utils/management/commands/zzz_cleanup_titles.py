
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

    def handle(self, *args, **options):
        """Checks existing journal settings, adds missing ones.

        :param args: None
        :param options: None
        :return: None
        """
        dryrun = options.get('dryrun', True)
        fileout = options.get('fileout', 'result.xlsx')
        pk = options.get('pk', None)

        wb = xlsxwriter.Workbook(fileout)
        sheet = wb.add_worksheet('titles')
        sheet.freeze_panes(1, 0)

        row = 0
        col = iter(range(0,30))
        sheet.write(row,next(col),'id')
        sheet.write(row,next(col),'language')
        sheet.write(row,next(col),'title')
        sheet.write(row,next(col),'title_en')
        sheet.write(row,next(col),'title_de')
        sheet.write(row,next(col),'title_de_tuw')
        sheet.write(row,next(col),'subtitle')
        sheet.write(row,next(col),'subtitle_en')
        sheet.write(row,next(col),'subtitle_de')
        sheet.write(row,next(col),'subtitle_de_tuw')
        sheet.write(row,next(col),'abstract')
        sheet.write(row,next(col),'abstract_en')
        sheet.write(row,next(col),'abstract_de')
        sheet.write(row,next(col),'abstract_de_tuw')
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

            # no parallel title
            # article language german
            # english title set
            # >> delete english title
            if language == 'deu' and title and title_en and title_de and not title_de_tuw:
                l.append('delete english title')
                article.__dict__['title_en'] = None
                if not dryrun:
                    article.save()

            # no parallel title
            # article language english
            # german title set
            # >> delete german title
            if language == 'eng' and title and title_en and title_de and not title_de_tuw:
                l.append('delete german title')
                article.__dict__['title_de'] = None
                if not dryrun:
                    article.save()

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
                if not dryrun:
                    article.save()

            row += 1 
            col = iter(range(0,30))
            sheet.write(row,next(col),article.pk)
            sheet.write(row,next(col),language)
            sheet.write(row,next(col),title)
            sheet.write(row,next(col),title_en)
            sheet.write(row,next(col),title_de)
            sheet.write(row,next(col),title_de_tuw)
            sheet.write(row,next(col),subtitle)
            sheet.write(row,next(col),subtitle_en)
            sheet.write(row,next(col),subtitle_de)
            sheet.write(row,next(col),subtitle_de_tuw)
            sheet.write(row,next(col),abstract)
            sheet.write(row,next(col),abstract_en)
            sheet.write(row,next(col),abstract_de)
            sheet.write(row,next(col),abstract_de_tuw)
            sheet.write(row,next(col),'; '.join(l))

        sheet = wb.add_worksheet('titles after change')
        sheet.freeze_panes(1, 0)

        row = 0
        col = iter(range(0,30))
        sheet.write(row,next(col),'id')
        sheet.write(row,next(col),'language')
        sheet.write(row,next(col),'title')
        sheet.write(row,next(col),'title_en')
        sheet.write(row,next(col),'title_de')
        sheet.write(row,next(col),'title_de_tuw')
        sheet.write(row,next(col),'subtitle')
        sheet.write(row,next(col),'subtitle_en')
        sheet.write(row,next(col),'subtitle_de')
        sheet.write(row,next(col),'subtitle_de_tuw')
        sheet.write(row,next(col),'abstract')
        sheet.write(row,next(col),'abstract_en')
        sheet.write(row,next(col),'abstract_de')
        sheet.write(row,next(col),'abstract_de_tuw')

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
            sheet.write(row,next(col),article.pk)
            sheet.write(row,next(col),language)
            sheet.write(row,next(col),title)
            sheet.write(row,next(col),title_en)
            sheet.write(row,next(col),title_de)
            sheet.write(row,next(col),title_de_tuw)
            sheet.write(row,next(col),subtitle)
            sheet.write(row,next(col),subtitle_en)
            sheet.write(row,next(col),subtitle_de)
            sheet.write(row,next(col),subtitle_de_tuw)
            sheet.write(row,next(col),abstract)
            sheet.write(row,next(col),abstract_en)
            sheet.write(row,next(col),abstract_de)
            sheet.write(row,next(col),abstract_de_tuw)

        wb.close()
    
