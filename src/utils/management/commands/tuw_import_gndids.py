import codecs
import os
import json
import re
import requests
from collections import OrderedDict

from django.core.management.base import BaseCommand
from django.utils import translation
from django.conf import settings

from core import models as core_models
from utils import setting_handler

class Command(BaseCommand):
    """A management command to add missing default settings to journals."""

    help = "Adds missing default settings to journals."

    def add_arguments(self, parser):
        """ Adds arguments to Django's management command-line parser.

        :param parser: the parser to which the required arguments will be added
        :return: None
        """
        parser.add_argument('--orcid', default=None)

    def handle(self, *args, **options):
        """Checks existing journal settings, adds missing ones.

        :param args: None
        :param options: None
        :return: None
        """
        orcid = options.get('orcid', None)
    
        if orcid:
            users = core_models.Account.objects.filter(orcid=orcid)
        else:
            users = core_models.Account.objects.filter(orcid__isnull=False)
        for user in users:
            if match := re.match('\d{4}-\d{4}-\d{4}-\d{4}',user.orcid):
                
                url = 'https://lobid.org/gnd/search?q='+user.orcid

                r = requests.request(method='GET',url=url)
                o = json.loads(r.text)
                cnt = o.get('totalItems')
                if cnt == 0:
                    print (f"no match found for {user.orcid}")
                elif cnt > 1:
                    print (f"{cnt} matches found for {user.orcid}")
                else:
                    member = o['member'][0] 
                    gndid = member.get('gndIdentifier')
                    if gndid:
                        print (f"match found for {user.orcid} : {gndid}")
                        user.gndid = gndid
                        user.save()
                    else:
                        print (f"match found for {user.orcid}, but no gndid!?!")