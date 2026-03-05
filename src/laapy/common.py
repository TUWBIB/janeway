import re
from lxml import etree

OPT_OPTIONS = 'options'
OPT_OPTIONS_TIMEOUT = 'timeout'
OPT_OPTIONS_ERROR_THRESHOLD = 'error_threshold'
OPT_OPTIONS_TARGET = 'target'
OPT_OPTIONS_LOGLEVEL = 'loglevel'
OPT_KEYS = 'keys'
OPT_KEYS_PRODUCTION = 'production'
OPT_KEYS_SANDBOX = 'sandbox'
OPT_KEYS_ANALYTICS = 'analytics'
OPT_DATABASE = 'database'
OPT_DATABASE_HOST = 'host'
OPT_DATABASE_PORT = 'port'
OPT_DATABASE_DATABASE = 'database'
OPT_DATABASE_USER = 'user'
OPT_DATABASE_PASSWORD = 'password'
OPT_DATABASE_LABEL = 'label'
OPT_DATABASE_ACTIVE = 'active'
OPT_CACHE = "cache"
OPT_CACHE_DIR = "dir"
OPT_CACHE_VALIDITY ="validity"
OPT_CACHE_ACTIVE = "active"
OPT_CACHE_URLPATTERNS = "urlpatterns"

ENV_OPTION_TIMEOUT = 'LAAPY_TIMEOUT'
ENV_OPTION_ERROR_THRESHOLD = 'LAAPY_ERROR_THRESHOLD'
ENV_OPTION_APITARGET = 'LAAPY_APITARGET'
ENV_APIKEY_PROUCTION = 'LAAPY_APIKEY_PRODUCTION'
ENV_APIKEY_SANDBOX = 'LAAPY_APIKEY_SANDBOX'
ENV_APIKEY_ANALYTICS = 'LAAPY_APIKEY_ANALYTICS'
ENV_DB_HOST = 'LAAPY_DB_HOST'
ENV_DB_PORT = 'LAAPY_DB_PORT'
ENV_DB_USER = 'LAAPY_DB_USER'
ENV_DB_PASSWORD = 'LAAPY_DB_PASSWORD'
ENV_DB_DATABASE = 'LAAPY_DB_DATABASE'
ENV_DB_LABEL = 'LAAPY_DB_LABEL'
ENV_DB_ACTIVE = 'LAAPY_DB_ACTIVE'
ENV_CACHE_DIR = "LAAPY_CACHE_DIR"
ENV_CACHE_VALIDITY = "LAAPY_CACHE_VALIDITY"
ENV_CACHE_ACTIVE = "LAAPY_CACHE_ACTIVE"

API_TARGET_SANDBOX = 'sandbox'
API_TARGET_PRODUCTION = 'production'
API_TARGETS = [API_TARGET_SANDBOX, API_TARGET_PRODUCTION]

API_ERROR_USER_WITH_IDENTIFIER_X_OF_TYPE_Y_WAS_NOT_FOUND = '401890'
API_ERROR_USER_WITH_IDENTIFIER_X = '401861'
API_ERROR_SEARCH_FAILED_FOR_TITLES = '402203'
API_ERROR_SEARCH_FAILED_FOR_HOLDINGS = '402208'
API_ERROR_FAILED_TO_SCAN_IN_ITEM = "402502"
"""Failed to scan in item. Error details: com.exlibris.urm.fulfillment.exceptions.FulfillmentException: Both item and request barcodes are empty"""


DC_FIELD_TITLE = 'title'
DC_FIELD_CREATOR = 'creator'
DC_FIELD_SUBJECT = 'subject'
DC_FIELD_DESCRIPTION = 'description'
DC_FIELD_PUBLISHER = 'publisher'
DC_FIELD_TYPE = 'type'
DC_FIELD_FORMAT = 'format'
DC_FIELD_IDENTIFIER = 'identifier'
DC_FIELD_SOURCE = 'source'
DC_FIELD_LANGUAGE = 'language'
DC_FIELD_RELATION = 'relation'
DC_FIELD_COVERAGE = 'coverage'
DC_FIELD_RIGHTS = 'rights'
DC_FIELD_DATE = 'date'
DC_FIELDS = [ DC_FIELD_TITLE, DC_FIELD_CREATOR, DC_FIELD_SUBJECT, DC_FIELD_DESCRIPTION, DC_FIELD_PUBLISHER, DC_FIELD_TYPE, DC_FIELD_FORMAT,
    DC_FIELD_IDENTIFIER, DC_FIELD_SOURCE, DC_FIELD_LANGUAGE, DC_FIELD_RELATION, DC_FIELD_COVERAGE, DC_FIELD_RIGHTS, DC_FIELD_DATE ]

MARC21_DC_MAP_GENERIC = 'generic'
MARC21_DC_MAP_HSS = 'hss'
MARC21_DC_MAP_OES_JFM = 'oes_jfm'

# strip encoding declaration
# etree complains otherwise
def stripXmlDeclaration(xml):
    pattern = re.compile('<\?xml.+?\?>')
    xml = pattern.sub('',xml)
    return xml

def addXmlDeclaration(xml):
    match=re.match(r'^<\?xml version="1.0" encoding="UTF-8" standalone="yes"\?>',xml)
    if match:
        return xml
    else:
        return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'+xml

def prettyPrint(xml):
    node = etree.fromstring(stripXmlDeclaration(xml))
    xml = etree.tostring(node, pretty_print=True).decode("utf-8")

    return xml


