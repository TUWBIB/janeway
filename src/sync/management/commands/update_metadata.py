import os
import sys
import time
import re
import traceback

from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db import transaction
from django.utils import translation

from journal import models as journal_models
from submission import models as submission_models
from sync import logic,views
from sync.datacite import api as datacite_api

class Command(BaseCommand):

    help = "Updates article metadata stored @Datacite"
    op = None
    article_id = None
    journal_code = None
    journal = None
    api = None

    def add_arguments(self, parser):
        parser.add_argument('operation', nargs='?', default=None)
        parser.add_argument('journal_code', nargs='?', default=None)
        parser.add_argument('article_id', nargs='?', default=None)

    def handle(self, *args, **options):
        self.op = options.get('operation', None)
        self.journal_code = options.get('journal_code', None)
        self.article_id = options.get('article_id', None)

        if self.op not in ['updatemd']:
            print ("invalid operation")
            sys.exit(0)


        if self.journal_code is None:
            print ("Journal code needs to be specified")
            sys.exit(0)

        if self.article_id is None:
            print ("Article id needs to be specified")
            sys.exit(0)

        if self.op == 'updatemd' and self.journal_code != 'JFM':
            print ("Op updatemd")
            sys.exit(0)


        foo_id = None
        try:
            foo_id = int(self.article_id)
        except:
            pass
        if foo_id is None and self.article_id !='ALL':
            print ("Article id needs to be numeric or *ALL*")
            sys.exit(0)

        try:
            self.journal = journal_models.Journal.objects.get(code=self.journal_code)
        except:
            print ("No journal with code {} found.".format(self.journal_code))
            sys.exit(0)

        if self.op == 'updatemd':
            self.op_updateMetadata()

    def op_updateMetadata(self):
        try:
            self.api=datacite_api.API()
        except Exception as e:
            print (traceback.format_exc())

        if self.article_id == 'ALL':
            articles = submission_models.Article.objects.filter(journal=self.journal)
        else:
            articles = submission_models.Article.objects.filter(pk=int(self.article_id),journal=self.journal)
            if len(articles) == 0:
                print ("No article with id {} found.".format(self.article_id))
                sys.exit(0)

        for article in articles:
            time.sleep(0.5)
            article = submission_models.Article.objects.get(pk=article.id)
            doi = article.get_doi()

            print ("processing article: {} {} {}".format(article.id,article.title,doi))
            if doi is None:
                print ("\tno doi skipping...")
                continue

            (xml, errors, warnings) = logic.articleToDataCiteXML(article.id)
            if errors:
                print ('\n'.join(errors))
                sys.exit(0)

            if warnings:
                print ('\n'.join(warnings))

            (status,content)=self.api.updateMetadata(doi,xml)
            if status == "success":
                print ("\tdone")
            else:
                errors=[]
                errors.append(content)
                print ('\n'.join(errors))
                sys.exit(0)
    




#            new_url = 'https://journal.ifm.tuwien.ac.at/article/id'+str(article.id)
#
#            self.update_datacite_url_to_janeway_url(article,new_url)
#            time.sleep(0.5)





