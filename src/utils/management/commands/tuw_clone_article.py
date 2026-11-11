import codecs
import os
import json
import re
import requests
from collections import OrderedDict

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
        parser.add_argument('--id', default=None)

    def handle(self, *args, **options):
        """Checks existing journal settings, adds missing ones.

        :param args: None
        :param options: None
        :return: None
        """
        id = options.get('id', None)
    
        
        article = submission_models.Article.objects.get(pk=id)
        article.pk = None
        article.save()
        new_pk = article.pk 
        new = submission_models.Article.objects.get(pk=new_pk)
        article = submission_models.Article.objects.get(pk=id)
        for x in article.authors.all():
            new.authors.add(x)
        new.save()
        new.snapshot_authors()

        print(f"article cloned, new id {new.pk}")
