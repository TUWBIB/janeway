import codecs
import os
import json
from collections import OrderedDict

from django.core.management.base import BaseCommand
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
        parser.add_argument('--filename', required=True)

    def handle(self, *args, **options):
        """Synchronizes settings to journals.

        :param args: None
        :param options: None
        :return: None
        """
        translation.activate('en')
        filename = options.get('filename',None)

        with codecs.open(filename, 'r+', encoding='utf-8') as json_data:
            default_data = json.load(json_data, object_pairs_hook=OrderedDict)

            with transaction.atomic():

                for o in default_data:
                    setting_name = o['setting']['name']
                    setting_group_name = o['group']['name']
                    l_editable_by = o['editable_by']

                    l_role = []
                    for v in l_editable_by:
                        role = core_models.Role.objects.get(slug=v)
                        l_role.append(role)

                    d_value = o['value']
                    for journal_code,value in d_value.items():

                        journal = None if journal_code == 'default' else journal_models.Journal.objects.get(code=journal_code)
                        group,_ = core_models.SettingGroup.objects.get_or_create(name=setting_group_name)
                        setting,setting_created = core_models.Setting.objects.get_or_create(name=setting_name,group=group)
                        if setting_created:
                            setting.description = o['setting']['description']
                            setting.is_translatable = o['setting']['is_translatable']
                            setting.pretty_name = o['setting']['pretty_name']
                            setting.editable_by.clear()
                            for v in l_role:
                                setting.editable_by.add(v)
                            setting.save()
                        setting_value,_ = core_models.SettingValue.objects.get_or_create(setting=setting,journal=journal)

                        if not isinstance(value,str):
                            value = json.dumps(value,ensure_ascii=False)

                        setting_value.value = value
                        setting_value.save()
                        print (f"setting saved, {setting_name} for {journal_code} with {value}")
