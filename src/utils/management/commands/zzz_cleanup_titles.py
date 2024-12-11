
from django.core.management.base import BaseCommand
from django.utils import translation
from django.conf import settings

from submission import models as submission_models

class Command(BaseCommand):
    """A management command to add missing default settings to journals."""

    help = "Adds missing default settings to journals."

    def add_arguments(self, parser):
        """ Adds arguments to Django's management command-line parser.

        :param parser: the parser to which the required arguments will be added
        :return: None
        """
        parser.add_argument('--dryrun', default=True)

    def handle(self, *args, **options):
        """Checks existing journal settings, adds missing ones.

        :param args: None
        :param options: None
        :return: None
        """
        WARN_TITLE_TUW_SET = 'title tuw set'
        WARN_ARTICLE_LANGUAGE_ENGLISH_TITLE_EN_NOT_SET = 'english article, but english title not set'
        WARN_ARTICLE_LANGUAGE_GERMAN_TITLE_DE_NOT_SET = 'german article, but german title not set'

        dryrun = options.get('dryrun', True)

        articles = submission_models.Article.objects.all().order_by('id')
        count = 0
        for article in articles:
            l = []
            warnings = []
#            l.append(str(article.journal.id))
            title = article.__dict__.get('title','')
            title_en = article.__dict__.get('title_en','')
            title_de = article.__dict__.get('title_de','')
            title_de_tuw = article.title_de_tuw if article.title_de_tuw else ''
            language = article.language
            if title is None: title = ''
            if title_en is None: title_en = ''
            if title_de is None: title_de = ''
            if language is None: language = ''

            l.append(str(article.pk))
            l.append(language)                        
            l.append(f'title = {title}')
            l.append(f'title_en = {title_en}')
            l.append(f'title_de = {title_de}')
            l.append(f'title_de_tuw = {title_de_tuw}')

            s = ';'.join(l)
            if language == 'deu' and not title_de:
                warnings.append(WARN_ARTICLE_LANGUAGE_GERMAN_TITLE_DE_NOT_SET)
            if language == 'eng' and not title_en:
                warnings.append(WARN_ARTICLE_LANGUAGE_ENGLISH_TITLE_EN_NOT_SET)
            if title_de_tuw:
                warnings.append(WARN_TITLE_TUW_SET)

            if warnings:
                count += 1
                print(s)            
                print(warnings)
                
        print(f'{count} articles with warnings')




    
