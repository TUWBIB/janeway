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
        parser.add_argument('--ignore-settings', required=False)
        parser.add_argument('--restrictto-settings', required=False)
        parser.add_argument('--overwrite', required=False)
        parser.add_argument('--journal-codes', required=False)

    def handle(self, *args, **options):
        """Synchronizes settings to journals.

        :param args: None
        :param options: None
        :return: None
        """
        translation.activate('en')

        print(options)

        filename = options.get('filename',None)
        ignore_settings = options.get('ignore_settings',None)
        ignore_settings = [] if ignore_settings is None else ignore_settings.split(',') 
        restrictto_settings = options.get('restrictto_settings',None)
        restrictto_settings = [] if restrictto_settings is None else restrictto_settings.split(',') 
        journal_codes = options.get('journal_codes',None)
        journal_codes = [] if journal_codes is None else journal_codes.split(',') 
        overwrite = options.get('overwrite',"True")
        overwrite = "True" if overwrite is None else overwrite
        overwrite = False if overwrite.lower() == 'false' else True


        with codecs.open(filename, 'r+', encoding='utf-8') as json_data:
            default_data = json.load(json_data, object_pairs_hook=OrderedDict)

            with transaction.atomic():

                for o in default_data:
                    setting_name = o['setting']['name']

                    if setting_name in ignore_settings:
                        print (f"setting ignored, {setting_name}")
                        continue

                    if restrictto_settings and setting_name not in restrictto_settings:
                        print (f"setting ignored, {setting_name}")
                        continue

                    setting_group_name = o['group']['name']
                    l_editable_by = o['editable_by']

                    l_role = []
                    for v in l_editable_by:
                        role = core_models.Role.objects.get(slug=v)
                        l_role.append(role)

                    d_value = o['value']
                    for journal_code,value in d_value.items():
                        if journal_codes and journal_code not in journal_codes:
                            print (f"setting ignored, {setting_name} due to journal {journal_code} not in parameter list")
                            continue

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
                        setting_value,value_created = core_models.SettingValue.objects.get_or_create(setting=setting,journal=journal)

                        if not isinstance(value,str):
                            value = json.dumps(value,ensure_ascii=False)

                        if value_created:
                            setting_value.value = value
                            setting_value.save()
                            print (f"setting saved, {setting_name} for {journal_code} with {value}")                            
                        else:
                            if overwrite:
                                setting_value.value = value
                                setting_value.save()
                                print (f"setting saved, {setting_name} for {journal_code} with {value}")                                                            
                            else:
                                print (f"overwrite false, setting not changed, {setting_name} for {journal_code} with {value},kept value {setting_value.value}")
                        
