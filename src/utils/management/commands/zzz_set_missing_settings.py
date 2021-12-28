import codecs
import os
import json
from collections import OrderedDict

from django.core.management.base import BaseCommand
from django.utils import translation
from django.conf import settings

from core import models as core_models
from journal import models as journal_models
from utils import setting_handler
from utils import install


class Command(BaseCommand):
    """A management command to add missing default settings to journals."""

    help = "Adds missing default settings to journals."

    def add_arguments(self, parser):
        """ Adds arguments to Django's management command-line parser.

        :param parser: the parser to which the required arguments will be added
        :return: None
        """
        parser.add_argument('--journal_code', default=None)

    def handle(self, *args, **options):
        """Checks existing journal settings, adds missing ones.

        :param args: None
        :param options: None
        :return: None
        """
        translation.activate('en')
        journal_code = options.get('journal_code', None)

        with codecs.open(os.path.join(settings.BASE_DIR, 'utils/install/journal_defaults.json'), 'r+', encoding='utf-8') as json_data:
            default_data = json.load(json_data, object_pairs_hook=OrderedDict)
    
        if journal_code:
            journals = journal_models.Journal.objects.filter(code=journal_code)
        else:
            journals = journal_models.Journal.objects.all()
        
        for journal in journals:
            install.update_settings(journal,management_command=True)
            for o in default_data:
                setting_name = o['setting']['name']
                setting_group_name = o['group']['name']
                default_value = o['value']['default']

                try:
                    setting_handler.get_setting(setting_group_name=setting_group_name,setting_name=setting_name,journal=journal)
                except Exception as e:
                    print (f'setting not found {journal.code}, {setting_group_name}, {setting_name}')
                    try:
                        group = core_models.SettingGroup.objects.get(
                            name=setting_group_name
                        )
                    except:
                        group = core_models.SettingGroup.objects.get(
                            name=setting_group_name
                        )
                        setting_group_name='Plugin:'+setting_group_name

                    setting = core_models.Setting.objects.get_or_create(
                        name=setting_name,
                        group=group,
                    )
                    setting_handler.save_setting(setting_group_name=setting_group_name,setting_name=setting_name,journal=journal,value=default_value)