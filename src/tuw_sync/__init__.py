import json

from django.conf import settings
from laapy import API
from .datacite import api as dcapi

datacite_settings = settings.DATACITE
alma_settings = settings.ALMA
alma_api = API(json_str=json.dumps(settings.LAAPY))
datacite_api = dcapi.API(json_str=json.dumps(settings.DATACITE))

