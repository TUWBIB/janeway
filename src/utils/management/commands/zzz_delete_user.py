import codecs
import os
import json
from collections import OrderedDict

from django.core.management.base import BaseCommand

from core import models as core_models


class Command(BaseCommand):
    """Deletes a user account based on id. No questions asked.."""

    help = "Deletes a user with the given id."

    def add_arguments(self, parser):
        """ Adds arguments to Django's management command-line parser.

        :param parser: the parser to which the required arguments will be added
        :return: None
        """
        parser.add_argument('--userid', required=True)

    def handle(self, *args, **options):
        """Deletes a user account based on id. No questions asked.

        :param args: None
        :param options: None
        :return: None
        """

        user_id = options.get('userid',None)        
        user = core_models.Account.objects.get(pk=user_id)
        user.delete()
