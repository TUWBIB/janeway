import codecs
import os
import json
import traceback
import re
from collections import OrderedDict

import openpyxl

from django.core.management.base import BaseCommand
from django.core.cache import cache
from django.utils import translation
from django.conf import settings
from django.db import transaction

from journal import models as journal_models
from core import models as core_models

class Command(BaseCommand):
    """A management command to synchronize all default settings to all journals."""

    help = "Synchronizes unspecified default settings to all journals."

    def add_arguments(self, parser):
        """ Adds arguments to Django's management command-line parser.

        :param parser: the parser to which the required arguments will be added
        :return: None
        """
        subparsers = parser.add_subparsers(dest="mode", required=True, help="Available mode: import")
        import_parser = subparsers.add_parser("import")
        import_parser.add_argument('filename')


#                        account=findCreateAccount(author)
#                                order+=1
#                                frozenauthor=submission_models.FrozenAuthor.objects.create(
#                                        author=account,
#                                        article=article,
#                                        first_name=author.getFirstName(),
#                                        last_name=author.getLastName(),
#                                        order=order,
#                                        institution=''
#                                )
#                                submission_models.ArticleAuthorOrder.objects.create(
#                                        author=account,
#                                        article=article,
#                                        order=order
#                                )
#                                article.authors.add(account)



    def handle(self, *args, **options):
        """Synchronizes settings to journals.

        :param args: None
        :param options: None
        :return: None
        """
        
        map_email_account = {}

        def readExcel(filename):
            nonlocal map_email_account            
            error = 0
            try:
                wb = openpyxl.load_workbook(filename, read_only=True,data_only=True)
                ws = wb.active
                row_idx = 1
                for row in ws.iter_rows(min_row=2, max_col=5, values_only=True):
                    if row[0] is None:
                        break

                    row_idx += 1
                    
                    names = str(row[0]).strip()
                    emails = str(row[1]).strip()
                    l_person = names.split(';')
                    l_email = emails.split(';')

                    if len(l_person) != len(l_email):
                        error = 1

                    if error: break                        

                    for i in range(0,len(l_person)):
                        account = core_models.Account()
                        account.email = l_email[i]
                        account.email = account.email.strip()
                        s = l_person[i]
                        groups = re.match(r"^(.*?)\s+([^\s]+)\s+(\(.*\))\*?$",s)
                        account.first_name = groups[1]
                        account.first_name = account.first_name.strip()
                        account.last_name = groups[2]
                        account.last_name = account.last_name.strip()
                        account.affiliation = groups[3]
                        account.affiliation = account.affiliation.replace('(','')
                        account.affiliation = account.affiliation.replace(')','')
                        account.affiliation = account.affiliation.replace('*','')
                        account.affiliation = account.affiliation.strip()
                        account.username = account.email
                        account.password = ''
                        account.is_active = 0
                        account.is_admin = 0
                        account.is_superuser = 0
                        account.is_staff = 0

                        if account.email not in map_email_account:
                            map_email_account[account.email] = account

            except Exception as e:
                print(f"exception={type(e).__name__}")
                print(f"stacktrace={traceback.format_exc()}")
            finally:
                wb.close()



            if error:
                exit(1)

        mode = options.get('mode',None)
        if mode == 'import':
            filename = options.get('filename',None)
            readExcel(filename)

            with transaction.atomic():
                for k,v in map_email_account.items():
                    accounts = core_models.Account.objects.filter(email=k)
                    if accounts:
                        print(f"{k} already exists")
                    else:
                        v.save()
                        print(f"{k} created, {v.first_name}, {v.last_name}, {v.affiliation}")

                cache.clear()                                        


