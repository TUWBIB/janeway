import os
import sys
 
from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db import transaction
from django.utils import translation

from press import models as press_models
from journal import models as journal_models
from submission import models as submission_models
from utils.alma import api as alma_api,marc as alma_marc,alma as alma


class Command(BaseCommand):
    help = "Syncs a record with Alma"

    def add_arguments(self, parser):
        parser.add_argument(
            '-m', '--marc_only',
            action='store_true',
            dest='marc_only',
            default=False,
            help='Shows MARC-21 record which is exported',
        )

    def handle(self, *args, **options):
        print("Please answer the following questions.\n")

        marc_only=options['marc_only']
        article_id = input('Janeway Id of article to export: ')
        try:
            article = submission_models.Article.objects.get(pk=article_id)
        except:
            print ("No article with id {} found.".format(article_id))
            sys.exit(0)


        api=alma_api.API()
        api.setAPITarget("sandbox")
        xml=alma.toMarc(article_id)
        xml=api.addXmlDeclaration(xml)
        print (xml)
#        api.createBibRecord(xml)

