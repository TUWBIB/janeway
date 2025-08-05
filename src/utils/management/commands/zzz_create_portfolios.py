import codecs
import os
import json
import traceback
import re
from collections import OrderedDict


from django.db.models import Q
from django.core.management.base import BaseCommand
from django.utils import translation
from django.conf import settings

from core import settings
from core import models as core_models
from journal import models as journal_models
from submission import models as submission_models

from utils import setting_handler
from utils import install

import laapy


class Command(BaseCommand):
    """A management command to add missing default settings to journals."""

    help = "Adds missing default settings to journals."

    def add_arguments(self, parser):
        """ Adds arguments to Django's management command-line parser.

        :param parser: the parser to which the required arguments will be added
        :return: None
        """
        parser.add_argument('--journal_code', default=None)
        parser.add_argument('--max', default=None)
        parser.add_argument('--offset', default=None)
        parser.add_argument('--mmsid', default=None)

    def handle(self, *args, **options):
        """Checks existing journal settings, adds missing ones.

        :param args: None
        :param options: None
        :return: None
        """

        try:
            api = laapy.API(json_str=json.dumps(settings.LAAPY))
            alma_portfolios = settings.ALMA_PORTFOLIOS
        except Exception as e:
            print("error in configuration")
            exit(1)

        create_portfolios = alma_portfolios.get('create_portfolios',False)
        if not create_portfolios:
            print("creating portfolios disabled in config. exiting.")
            exit(0)

        collectionid = alma_portfolios.get('collection_id', None)
        serviceid = alma_portfolios.get('service_id', None)

        if not collectionid or not serviceid:
            print("error. collectionid or serviceid not set in config")
            exit(1)

        journal_code = options.get('journal_code', None)
        max_records = options.get('max', None)
        if max_records: max_records = int(max_records)
        offset = options.get('offset',None)
        offset = int(offset) if offset else 0
        mmsid_to_process = options.get('mmsid', None)
        if mmsid_to_process: mmsid_to_process = str(mmsid_to_process)
        if journal_code:
            articles = submission_models.Article.objects.filter(
                Q(journal__code = journal_code)
                ).order_by('journal__code','id')
        else:
            articles = submission_models.Article.objects.all().order_by('journal__code','id')

        for i,article in enumerate(articles):
            if i < offset:
                continue

            if max_records and i >= (max_records + offset):
                break

            print(f"processing #{i} {article.journal.code} {article.id} {article.title}")
            mmsid = article.get_identifier('mmsid')
            if not mmsid:
                print(f"\t skipping, no mmsid")
                continue
            doi = article.get_identifier('doi')
            if not doi:
                print(f"\t skipping, no doi")
                continue

            print(f"\t mmsid: {doi}")

            if mmsid_to_process and mmsid_to_process.strip() != mmsid.strip():
                print(f"\t skipping, mmsid not in parms")
                continue

            result = api.getPortfolios(mmsid)
            xml = result.data
            errs = result.errs
            if errs:
                for err in errs:
                    print(err)
                exit(1)
            
            match = re.search(r'<portfolios total_record_count="(\d+)"',xml)
            if match:
                cnt = int(match.group(1))
                if cnt > 0:
                    print("\t skipping, portfolio already exists")
                    continue

            url = f"https://doi.org/{doi}"
            result = api.createPortfolio(collectionid,serviceid,mmsid,url)
            xml = result.data
            errs = result.errs
            if errs:
                for err in errs:
                    print(err)
                exit(1)


        







