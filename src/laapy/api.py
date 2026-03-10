from __future__ import annotations

# Laapy - lame alma api in python

import os
import sys
import re
import json
import threading
import traceback
import requests
import urllib.parse
import datetime
import logging
import csv
import uuid
import textwrap
from typing import List,Tuple
from lxml import etree
from pathlib import Path

head,tail=os.path.split(sys.path[0])
x = head
if x not in sys.path: sys.path.append(x)
x = os.path.join(head,tail)
if x not in sys.path: sys.path.append(x)

from .domain import Item, Set, SetMember, Fee, Transaction, Request, Holding, Portfolio
from .db import DB,LaapyDBInterface
from .common import addXmlDeclaration
from .common import OPT_OPTIONS, OPT_OPTIONS_LOGLEVEL, OPT_OPTIONS_TARGET, OPT_OPTIONS_ERROR_THRESHOLD, OPT_OPTIONS_TIMEOUT, \
    OPT_KEYS, \
    OPT_DATABASE, OPT_DATABASE_HOST, OPT_DATABASE_DATABASE, OPT_DATABASE_USER, OPT_DATABASE_PASSWORD, \
    OPT_DATABASE_LABEL, OPT_DATABASE_LABEL, OPT_DATABASE_ACTIVE, OPT_DATABASE_PORT, \
    OPT_KEYS_PRODUCTION, OPT_KEYS_SANDBOX, OPT_KEYS_ANALYTICS, \
    OPT_CACHE, OPT_CACHE_DIR, OPT_CACHE_VALIDITY, OPT_CACHE_ACTIVE, \
    OPT_CACHE_URLPATTERNS, \
    ENV_DB_ACTIVE, ENV_DB_USER, ENV_DB_PASSWORD, ENV_DB_DATABASE, ENV_DB_HOST, ENV_DB_PORT, ENV_DB_LABEL, \
    ENV_OPTION_APITARGET, ENV_OPTION_ERROR_THRESHOLD, ENV_OPTION_TIMEOUT, \
    ENV_APIKEY_PROUCTION, ENV_APIKEY_SANDBOX, ENV_APIKEY_ANALYTICS, \
    ENV_CACHE_DIR, ENV_CACHE_VALIDITY, ENV_CACHE_ACTIVE

class APIThread(threading.Thread):
    result:APIResult

    def __init__(self, group=None, target=None, name=None, args=None, kwargs=None):
        super().__init__(group=group, target=target, name=name, args=args, kwargs=kwargs)
        self.result = None

    def run(self):
        """Method representing the thread's activity.
        You may override this method in a subclass. The standard run() method
        invokes the callable object passed to the object's constructor as the
        target argument, if any, with sequential and keyword arguments taken
        from the args and kwargs arguments, respectively.
        """
        try:
            if self._target is not None:
                self.result = self._target(*self._args, **self._kwargs)
        finally:
            # Avoid a refcycle if the thread is running a function with
            # an argument that has a member that points to the thread.
            del self._target, self._args, self._kwargs

class APIResult():
    data:str
    errs:List[str]
    error_code:str
    error_message:str
    http_status:str
    from_cache:bool
    infos:List[str]

    def __init__(self) -> None:
        self.data = None
        self.errs = []
        self.error_code = None
        self.error_message = None
        self.http_status = None
        self.from_cache = False
        self.infos = []

    def __str__(self):
        return "data={} errs={} error_code={} error_message={} http_status={} from_cache = {} infos = {}".format(self.data,
            self.errs,self.error_code,self.error_message,self.http_status,self.from_cache,self.infos)

# used for no ops like unnecessary updates, eg. suppress an already suppressed holding
API_RESULT_NO_OP = APIResult()
class CacheLine():
    ts: str
    url: str
    apikey : str
    filename: str

    def __init__(self,ts:str,url:str,apikey:str,filename:str):
        self.ts = ts
        self.url = url
        self.apikey = apikey
        self.filename = filename

    def __str__(self):
        return "ts={} url={} apikey={} filename={}".format(self.ts,self.url,self.apikey,self.filename)

    def __eq__(self, other):
        if isinstance(other, type(self)):
            return self.url == other.url and self.apikey == other.apikey
        return False

    def __hash__(self):
        return hash(self.url) ^ hash(self.apikey)

    def to_csv(self) -> list[str]:
        l: list[str] = []
        l.append(self.ts)
        l.append(self.url)
        l.append(self.apikey)
        l.append(self.filename)
        return l

    @classmethod
    def from_csv_line(self,row):
        it = iter(row)
        ts = next(it)
        url = next(it)
        apikey = next(it)
        filename = next(it)
        return CacheLine(ts=ts,url=url,apikey=apikey,filename=filename)

logger = None

class API:
    global logger
    logger = logging.getLogger('laapy')

    ALMA_API_BASE ='https://api-eu.hosted.exlibrisgroup.com/almaws/v1/'
    API_CONF = ALMA_API_BASE + 'conf/'
    API_CONF_LETTERS = API_CONF + 'letters/'
    API_CONF_CODE_TABLES = API_CONF +'code-tables/'
    API_SETS = API_CONF + 'sets/'
    API_JOBS = API_CONF + 'jobs/'
    API_BIBS = ALMA_API_BASE + 'bibs/'
    API_USERS = ALMA_API_BASE + 'users/'
    API_ANALYTICS = ALMA_API_BASE + 'analytics/'
    API_E_COLLECTIONS = ALMA_API_BASE + 'electronic/e-collections/'
    API_TASK_LISTS = ALMA_API_BASE + 'task-lists/'
    RESPONSE_FORMAT='application/xml'
    INSTITUTION_CODE = '43ACC_TUW'

    error_count=0

    resultwrapper_lock = threading.Lock()

    cachelines: list[CacheLine] = []

    def __init__(self,obj_cfg=None,file_cfg=None,json_str=None,loglevel=None,db:LaapyDBInterface = None):
        """
        file_cfg: path to config file holding json data
        json_str: json as str
        """
        self.api_key = None
        self.api_target = None
        self.cfg = None
        self.db = None
        self.log_label = None
        data = None

        # prefer settings object if given
        # 2nd option is json str
        # 3rd option config file option
        # else defaults
        if obj_cfg:
            data = obj_cfg
            logging.debug("using object configuration")
        elif json_str:
            data = json.loads(json_str)
            logging.debug("using json configuration")
        else:
            # if config file given, try it
            if file_cfg is not None:
                file_cfg = Path(file_cfg)

                if not file_cfg.exists() or not file_cfg.is_file():
                    raise Exception(f'Laapy config file does not exist: {file_cfg}')

                with open(file_cfg,'r',encoding='utf-8') as file:
                    try:
                        data = json.load(file)
                    except Exception as e:
                        raise Exception(f'Laapy config file has errors: {e}')

                logging.debug(f"using json configuration from file {file_cfg}")
            else:
                file_cfg = Path(os.path.join(os.path.dirname(__file__),'api.json'))
                logging.info(f"trying default config file location {file_cfg}")

                if file_cfg.exists() and file_cfg.is_file():
                    logging.debug(f"using json configuration from default file {file_cfg}")
                    with open(file_cfg,'r',encoding='utf-8') as file:
                        try:
                            data = json.load(file)
                        except Exception as e:
                            raise Exception(f'default config exists, but has errors: {e}')

        if data is None: data = {}
        if OPT_OPTIONS not in data: data[OPT_OPTIONS] = {}
        if OPT_KEYS not in data: data[OPT_KEYS] = {}
        if OPT_DATABASE not in data: data[OPT_DATABASE] = {}
        if OPT_CACHE not in data: data[OPT_CACHE] = {}

        # override with environment
        if (x := os.environ.get(ENV_DB_HOST,None)): data[OPT_DATABASE][OPT_DATABASE_HOST] = x
        if (x := os.environ.get(ENV_DB_PORT,None)): data[OPT_DATABASE][OPT_DATABASE_PORT] = x
        if (x := os.environ.get(ENV_DB_USER,None)): data[OPT_DATABASE][OPT_DATABASE_USER] = x
        if (x := os.environ.get(ENV_DB_PASSWORD,None)): data[OPT_DATABASE][OPT_DATABASE_PASSWORD] = x
        if (x := os.environ.get(ENV_DB_DATABASE,None)): data[OPT_DATABASE][OPT_DATABASE_DATABASE] = x
        if (x := os.environ.get(ENV_DB_LABEL,None)): data[OPT_DATABASE][OPT_DATABASE_LABEL] = x
        if (x := os.environ.get(ENV_DB_ACTIVE,None)) and x.lower() == 'true': data[OPT_DATABASE][OPT_DATABASE_ACTIVE] = True
        if (x := os.environ.get(ENV_OPTION_TIMEOUT,None)): data[OPT_OPTIONS][OPT_OPTIONS_TIMEOUT] = x
        if (x := os.environ.get(ENV_OPTION_ERROR_THRESHOLD,None)): data[OPT_OPTIONS][OPT_OPTIONS_ERROR_THRESHOLD] = x
        if (x := os.environ.get(ENV_OPTION_APITARGET,None)): data[OPT_OPTIONS][OPT_OPTIONS_TARGET] = x
        if (x := os.environ.get(ENV_APIKEY_PROUCTION,None)): data[OPT_KEYS][OPT_KEYS_PRODUCTION] = x
        if (x := os.environ.get(ENV_APIKEY_SANDBOX,None)): data[OPT_KEYS][OPT_KEYS_SANDBOX] = x
        if (x := os.environ.get(ENV_APIKEY_ANALYTICS,None)): data[OPT_KEYS][OPT_KEYS_ANALYTICS] = x
        if (x := os.environ.get(ENV_CACHE_DIR,None)): data[OPT_CACHE][OPT_CACHE_DIR] = x
        if (x := os.environ.get(ENV_CACHE_VALIDITY,None)): data[OPT_CACHE][OPT_CACHE_VALIDITY] = x
        if (x := os.environ.get(ENV_CACHE_ACTIVE,None)) and x.lower() == 'true': data[OPT_CACHE][OPT_CACHE_ACTIVE] = x

        if not OPT_OPTIONS_ERROR_THRESHOLD in data[OPT_OPTIONS].keys():
            data[OPT_OPTIONS][OPT_OPTIONS_ERROR_THRESHOLD] = 0

        if not OPT_OPTIONS_TIMEOUT in data[OPT_OPTIONS].keys():
            data[OPT_OPTIONS][OPT_OPTIONS_TIMEOUT] = 0

        if OPT_OPTIONS_TARGET not in data[OPT_OPTIONS].keys():
            raise Exception(f'Laapy config error: option {OPT_OPTIONS_TARGET} needs to be set')

        target = data[OPT_OPTIONS][OPT_OPTIONS_TARGET]
        if target not in data[OPT_KEYS].keys():
            raise Exception(f'Laapy config error: no api key for target {target}')

        # make sure it's a boolean if set
        if OPT_CACHE in data and OPT_CACHE_ACTIVE in data[OPT_CACHE]:
            x = data[OPT_CACHE][OPT_CACHE_ACTIVE]
            data[OPT_CACHE][OPT_CACHE_ACTIVE] = True if x and x.lower() == 'true' else False

        self.cfg = data
        self.setAPITarget(target)
        self.setUseDatabaseLogging(db=db)

        if loglevel is None:
            loglevel = self.cfg[OPT_OPTIONS].get(OPT_OPTIONS_LOGLEVEL,"debug")
        loglevel = loglevel.upper()
        logger.setLevel(loglevel)

    def setAPITarget(self,key):
        if key in self.cfg[OPT_KEYS]:
            self.api_target = key
            self.api_key = self.cfg[OPT_KEYS][key]
        else:
            raise Exception('Laapy, invalid api target: '+key)

    def setDatabaseLogLabel(self,log_label):
        self.log_label = log_label

    def setUseDatabaseLogging(self,on_off=None,log_label=None,db=None):
        if on_off is None:
            on_off = self.cfg[OPT_DATABASE].get(OPT_DATABASE_ACTIVE,False)
            on_off = True if on_off == 'true' else False
        if log_label is None:
            log_label = self.cfg[OPT_DATABASE].get(OPT_DATABASE_LABEL,None)
        if self.db is not None:
            self.db.disconnect()
            self.db = None
        if on_off and OPT_DATABASE not in self.cfg.keys():
            raise Exception('database connection not configured')
        if on_off:
            self.log_label = log_label
            if db:
                self.db = db
            else:
                try:
                    self.db = DB(
                        self.cfg[OPT_DATABASE][OPT_DATABASE_HOST],
                        self.cfg[OPT_DATABASE][OPT_DATABASE_DATABASE],
                        self.cfg[OPT_DATABASE][OPT_DATABASE_USER],
                        self.cfg[OPT_DATABASE][OPT_DATABASE_PASSWORD],
                        self.cfg[OPT_DATABASE][OPT_DATABASE_PORT],
                    )
                    self.db.connect()
                except Exception as e:
                    logger.fatal(e)

    def setLogLevel(self,loglevel):
        loglevel = loglevel.upper()
        logger.setLevel(loglevel)

    def sendAPIRequest(self,url,type='GET',xml=None,json=None,apikey=None) -> APIResult:
        logger.info(f"url={url} method={type}")
        logger.debug(f"url={url} method={type} xml={xml} json={json}")

        result: APIResult = None
        timeout = int(self.cfg[OPT_OPTIONS][OPT_OPTIONS_TIMEOUT])

        if apikey is None: apikey = self.api_key

        errs = []
        r = None
        data = None

        # for logging
        callid = None
        status_code = None
        error_code = None
        error_message = None

        if self.db:
            try:
                body = json if json is not None else xml

                ts = datetime.datetime.now(datetime.timezone.utc)
                callid = self.db.beginCall(type,self.api_target,self.log_label,url,xml,ts)

            except Exception as e:
                logger.fatal(e)
                errs.append('Alma API error')
                errs.append(str(e))
                errs.append(traceback.format_exc())

            if errs:
                result = APIResult()
                result.errs = errs
                return result

        try:
            if self.cacheActive(url) and type in ['PUT', 'POST', 'DELETE']:
                self.invalidateCache(url)

            if self.cacheActive(url) and type == 'GET':
                result = self.readFromCache(url)
                if result:
                    return result

            result = APIResult()
            headers = {'Authorization' : apikey,
                        'Accept' : self.RESPONSE_FORMAT,
                    }

            if type == 'GET' or type == 'DELETE':
                r = requests.request(type,url,headers=headers,
                                     timeout=(timeout,timeout))
            elif type == 'PUT' or type == 'POST':
                if xml is not None:
                    headers['Content-Type']='application/xml; charset=utf-8'
                    r=requests.request(type,url,headers=headers,
                                       timeout=(timeout,timeout),
                                       data=xml.encode('utf-8'))
                elif json is not None:
                    r=requests.request(type,url,headers=headers,
                                       timeout=(timeout,timeout),
                                       json=json)
                else:
                    # fee payment is via post, but has no payload
                    r=requests.request(type,url,headers=headers,
                                       timeout=(timeout,timeout))
            else:
                raise NameError("Invalid request type {}".format(type))

            status_code = r.status_code
            data = r.text
            logger.debug(f"status={r.status_code} response={r.text}")

        except Exception as e:
            errs.append('Alma API error')
            errs.append(str(e))
            errs.append(traceback.format_exc())
            logger.error("exception={}".format(str(e)))
            logger.error("stacktrace={}".format(traceback.format_exc()))
            if r:
                errs.append(f"status={r.status_code} response={r.text}")
                logger.error(f"status={r.status_code} response={r.text}")

        if not errs:
            match = re.search('errorsExist',r.text)
            if match:
                errs.append('Alma API error')
                errs.append(r.text)

                error_code = None
                error_message = None
                match = re.search('<errorCode>(.+)</errorCode>',r.text,re.DOTALL)
                if match:
                    error_code=match[1]
                match = re.search('<errorMessage>(.+)</errorMessage>',r.text,re.DOTALL)
                if match:
                    error_message=match[1]

                logger.error(f"error_code={error_code} error_message={error_message}")

        if self.db:
            try:
                ts = datetime.datetime.now(datetime.timezone.utc)
                self.db.updateCall(ts,status_code,error_code,error_message,callid)
            except Exception as e:
                logger.fatal(e)
                errs.append('Alma API error')
                errs.append(str(e))
                errs.append(traceback.format_exc())

        result.data = data
        result.errs = errs
        result.error_code = error_code
        result.error_message = error_message
        result.http_status = status_code

        if type == 'GET':
            if self.cacheActive(url) and result and not result.errs:
                self.writeToCache(url,result)
        return result

    def deactivateCache(self):
        self.cfg[OPT_CACHE][OPT_CACHE_ACTIVE] = False

    def cacheActive(self,url):
        logger.debug('function {}'.format(sys._getframe(  ).f_code.co_name))
        if OPT_CACHE not in self.cfg or \
            OPT_CACHE_ACTIVE not in self.cfg[OPT_CACHE] or \
            not self.cfg[OPT_CACHE][OPT_CACHE_ACTIVE]:
            return False

        match = False
        patterns = self.cfg[OPT_CACHE][OPT_CACHE_URLPATTERNS]
        for pattern in patterns:
            match = re.search(pattern,url)
            if match:
                logger.debug("matched pattern {} for {}".format(pattern,url))
                break

        return match

    def readFromCache(self,url) -> APIResult:
        result: APIResult = None
        ts = datetime.datetime.now()
        if not self.cachelines:
            try:
                logger.debug('function {}'.format(sys._getframe(  ).f_code.co_name))

                line: CacheLine
                fileidx = os.path.join(self.cfg[OPT_CACHE][OPT_CACHE_DIR],'__INDEX.csv')

                if os.path.exists(fileidx):
                    with open(fileidx, 'r', encoding='utf-8') as file:
                        reader = csv.reader(file, delimiter=';', quotechar='|')
                        for row in reader:
                            line = CacheLine.from_csv_line(row)
                            self.cachelines.append(line)

            except Exception as e:
                self.cfg[OPT_CACHE][OPT_CACHE_ACTIVE] = False
                logger.error(e)
                logger.error("cache deactivated")
                return None

        current = CacheLine(apikey=self.api_key,ts=ts,url=url,filename='')
        filename: str = None
        for line in self.cachelines:
            if line == current:
                logger.info("cache, matching line found {}".format(line.to_csv()))
                tsline = datetime.datetime.strptime(line.ts,'%Y%m%d_%H%M%S')
                diff = ts - tsline
                if diff.seconds < self.cfg[OPT_CACHE][OPT_CACHE_VALIDITY]:
                    logger.info("cache, matching line also valid")
                    filename = line.filename
                    break
                else:
                    logger.info("cache, matching line found, but too old")

        if filename:
            filedata = os.path.join(self.cfg[OPT_CACHE][OPT_CACHE_DIR],filename)
            with open(filedata, 'r') as file:
                data = file.read()
                result = APIResult()
                result.data = data
                result.from_cache = True

        return result

    def invalidateCache(self,url:str):
        self.cachelines = []
        try:
            logger.debug('function {}'.format(sys._getframe(  ).f_code.co_name))

            line: CacheLine
            lines: list[CacheLine] = []
            ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            current = CacheLine(apikey=self.api_key,ts=ts,url=url,filename=str(uuid.uuid4()))
            filedata = None
            fileidx = os.path.join(self.cfg[OPT_CACHE][OPT_CACHE_DIR],'__INDEX.csv')

            if os.path.exists(fileidx):
                with open(fileidx, 'r', encoding='utf-8') as file:
                    reader = csv.reader(file, delimiter=';', quotechar='|')
                    for row in reader:
                        line = CacheLine.from_csv_line(row)
                        if line == current:
                            filedata = os.path.join(self.cfg[OPT_CACHE][OPT_CACHE_DIR],line.filename)
                            os.unlink(filedata)
                            logger.debug("cache: invalidated {} ".format(line.to_csv()))
                        else:
                            lines.append(line)

            with open(fileidx, 'w', encoding='utf-8') as file:
                writer = csv.writer(file, delimiter=';', quotechar='|')
                for line in lines:
                    writer.writerow(line.to_csv())

        except Exception as e:
            self.cfg[OPT_CACHE][OPT_CACHE_ACTIVE] = False
            logger.error(e)
            logger.error("cache deactivated")

    def writeToCache(self,url:str, result:APIResult):
        self.cachelines = []
        try:
            logger.debug('function {}'.format(sys._getframe(  ).f_code.co_name))

            line: CacheLine
            lines: list[CacheLine] = []
            replacement: bool = False
            ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            current = CacheLine(apikey=self.api_key,ts=ts,url=url,filename=str(uuid.uuid4()))

            filedata = os.path.join(self.cfg[OPT_CACHE][OPT_CACHE_DIR],current.filename)
            fileidx = os.path.join(self.cfg[OPT_CACHE][OPT_CACHE_DIR],'__INDEX.csv')

            if os.path.exists(fileidx):
                with open(fileidx, 'r', encoding='utf-8') as file:
                    reader = csv.reader(file, delimiter=';', quotechar='|')
                    for row in reader:
                        line = CacheLine.from_csv_line(row)
                        if line == current:
                            lines.append(current)
                            logger.debug("cache: replaced {} ".format(current.to_csv()))
                            replacement = True
                        else:
                            lines.append(line)
            if not replacement:
                lines.append(current)
                logger.debug("cache: added {} ".format(current.to_csv()))

            with open(fileidx, 'w', encoding='utf-8') as file:
                writer = csv.writer(file, delimiter=';', quotechar='|')
                for line in lines:
                    writer.writerow(line.to_csv())

            data = result.data
            dom = etree.fromstring(data.encode('utf-8'))
            data = etree.tostring(dom, pretty_print=True, encoding='utf-8', standalone=True)
            data = data.decode('utf-8')

            with open(filedata, 'w') as file:
                file.write(data)
        except Exception as e:
            self.cfg[OPT_CACHE][OPT_CACHE_ACTIVE] = False
            logger.error(e)
            logger.error("cache deactivated")

    def createBibRecord(self,xml,unsuppress=True,level=20) -> APIResult:
        url = self.API_BIBS
        l_subs = []

        if unsuppress:
            xml,cnt = re.subn('<suppress_from_publishing>true</suppress_from_publishing>','<suppress_from_publishing>false</suppress_from_publishing>',xml)
            if cnt == 0:
                l_subs.append('<suppress_from_publishing>false</suppress_from_publishing>')
        if level:
            xml,cnt = re.subn(r'<cataloging_level .*?>\d+</cataloging_level>','<cataloging_level>' + str(level) +'</cataloging_level>',xml)
            if cnt == 0:
                l_subs.append('<cataloging_level>' + str(level) +'</cataloging_level>')

        if l_subs:
            s = ''.join(l_subs)
            s += '<record>'
            xml = re.sub('<record>',s,xml)

        return self.sendAPIRequest(url,type='POST',xml=xml)

    def updateBibRecord(self,xml,mmsid) -> APIResult:
        url = self.API_BIBS + str(mmsid)
        return self.sendAPIRequest(url,type='PUT',xml=xml)

    def deleteBibRecord(self,mmsid,override=False) -> APIResult:
        url = self.API_BIBS + str(mmsid)
        if override:
            url += '?override=true'
        return self.sendAPIRequest(url,type='DELETE')

    def getBibRecord(self,mmsid) -> APIResult:
        url = self.API_BIBS + str(mmsid)
        return self.sendAPIRequest(url)
    
    def createHoldingRecord(self,mmsid,xml) -> APIResult:
        url = self.API_BIBS+str(mmsid)+'/holdings'
        return self.sendAPIRequest(url,type='POST',xml=xml)

    def getHoldingRecord(self,mmsid,holid) -> APIResult:
        url = self.API_BIBS+str(mmsid)+'/holdings/'+str(holid)
        return self.sendAPIRequest(url)

    def updateHoldingRecord(self,mmsid,holid,xml) -> APIResult:
        url = self.API_BIBS+str(mmsid)+'/holdings/'+str(holid)
        return self.sendAPIRequest(url,type='PUT',xml=xml)

    def getHoldings(self,mmsid) -> Tuple[List[Holding],APIResult]:
        url = self.API_BIBS+str(mmsid)+'/holdings/'
        result = self.sendAPIRequest(url)
        if result.errs:
            return None,result
        holdings = Holding.multiFromXml(result.data)
        return holdings, None
    
    def holSuppress(self,mmsid:str,holid:str,suppress:bool,xml=None) -> APIResult:
        """
        suppresses or unsuppresses a holding record
        """
        if not xml:
            result = self.getHoldingRecord(mmsid,holid)
            if result.errs:
                return result
            xml = result.data
        match = re.search(r'<suppress_from_publishing>(true|false)</suppress_from_publishing>',xml,flags=re.MULTILINE)
        current = match[1]
        if suppress and current == 'false':
            xml = re.sub('<suppress_from_publishing>false</suppress_from_publishing>','<suppress_from_publishing>true</suppress_from_publishing>',xml)
            return self.updateHoldingRecord(mmsid,holid,xml)
        elif not suppress and current == 'true':
            xml = re.sub('<suppress_from_publishing>true</suppress_from_publishing>','<suppress_from_publishing>false</suppress_from_publishing>',xml)
            return self.updateHoldingRecord(mmsid,holid,xml)
        else:
            return API_RESULT_NO_OP

    def deletePortfolio(self,mmsid,portfolioid) -> APIResult:
        url = self.API_BIBS + str(mmsid) + '/portfolios/' + str(portfolioid)
        return self.sendAPIRequest(url,type='DELETE')

    def getPortfolios(self,mmsid) -> APIResult:
        url = self.API_BIBS +str(mmsid) + '/portfolios/'
        return self.sendAPIRequest(url)

    def getPortfoliosAsObjects(self,mmsid) -> Tuple[List[Portfolio],APIResult]:
        url = self.API_BIBS +str(mmsid) + '/portfolios/'
        result = self.sendAPIRequest(url)
        if result.errs:
            return None,result
        portfolios = Portfolio.multiFromXml(result.data)
        return portfolios, None

    def getPortfolio(self,mmsid,portfolioid) -> APIResult:
        url = self.API_BIBS +str(mmsid) + '/portfolios/' + str(portfolioid)
        return self.sendAPIRequest(url)

    def createPortfolio(self,collectionid,serviceid,mmsid,link) -> APIResult:
        result: APIResult = None

        xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <portfolio>
            <is_local>true</is_local>
            <is_standalone>true</is_standalone>
            <resource_metadata>
                <mms_id link="{self.API_BIBS}{str(mmsid)}">{str(mmsid)}</mms_id>
            </resource_metadata>
            <electronic_collection>
                <id/>
                <service/>
            </electronic_collection>
            <availability desc="Available">11</availability>
            <material_type desc="Book">BOOK</material_type>
            <activation_date>{datetime.datetime.now().strftime("%Y-%m-%d")}.Z</activation_date>
            <expected_activation_date/>
            <library link="{self.ALMA_API_BASE}conf/libraries/EBOOK">EBOOK</library>
            <access_type/>
            <linking_details>
            <url/>
            <url_type>static</url_type>
            <dynamic_url/>
            <static_url>jkey={link}</static_url>
            <parser_parameters/>
            <parser_parameters_override/>
            <proxy_enabled desc="No">false</proxy_enabled>
            <proxy/>
            </linking_details>
            <coverage_details>
                <coverage_in_use desc="Only local">0</coverage_in_use>
                <global_date_information/>
                <local_date_information/>
            </coverage_details>
            <po_line/>
            <license/>
            <interface>
                <name/>
            </interface>
            <pda link=""/>
            <authentication_note/>
            <public_note/>
        </portfolio>
        '''
        
        if collectionid and serviceid:
            url = self.API_E_COLLECTIONS + str(collectionid) + '/e-services/' + str(serviceid) + '/portfolios/'
            result = self.sendAPIRequest(url,type='POST',xml=xml)
        else:
            url = self.API_BIBS + str(mmsid) + '/portfolios/'
            result = self.sendAPIRequest(url,type='POST',xml=xml)

        return result


    def getItemCount(self,mmsid,holdingid) -> Tuple[int,APIResult]:
        url = self.API_BIBS + str(mmsid) + '/holdings/' + str(holdingid) + '/items/' + '?offset=0&limit=0'
        result = self.sendAPIRequest(url)
        if result.errs:
            return None,result

        match = re.search(r'<items total_record_count="(\d+)"',result.data)
        if match:
            return int(match.group(1)),None
        else:
            result = APIResult()
            result.errs = ['cannot determine number of items']
            return None,result

    def getItems(self,mmsid,holid,**kwargs) -> Tuple[List[Item],APIResult]:
        number_of_items = 0
        offset = int(kwargs.get('offset',0))
        limit = int(kwargs.get('limit',100))
        if limit > 100: limit = 100

        # get no of items
        url = self.API_BIBS+str(mmsid)+'/holdings/'+str(holid)+'/items/'
        url += '?offset=0&limit=0'

        result = self.sendAPIRequest(url)
        if result.errs:
            return None,result

        match = re.search(r'<items total_record_count="(\d+)"',result.data)
        if match:
            number_of_items = int(match.group(1))
        else:
            result = APIResult()
            result.errs = ['cannot determine number of items']
            return None,result

        cnt = 0
        items = []
        ok = True

        while offset < number_of_items:
            url = self.API_BIBS + str(mmsid) + '/holdings/' + str(holid) + '/items'
            url += '?limit=' + str(limit) + '&offset=' + str(offset)
            result = self.sendAPIRequest(url)
            if result.errs:
                return None,result

            items.extend(Item.multiFromXml(result.data))
            offset += limit
            cnt += limit

        return items,None

    def getItem(self,mmsid,holid,itemid) -> APIResult:
        url = self.API_BIBS+str(mmsid)+'/holdings/'+str(holid)+'/items/'+str(itemid)
        return self.sendAPIRequest(url)

    def updateItem(self,mmsid,holid,itemid,xml) -> APIResult:
        url = self.API_BIBS+str(mmsid)+'/holdings/'+str(holid)+'/items/'+str(itemid)
        return self.sendAPIRequest(url,type='PUT',xml=xml)

    def deleteItem(self,mmsid,holid,itemid) -> APIResult:
        url = self.API_BIBS+str(mmsid)+'/holdings/'+str(holid)+'/items/'+str(itemid)
        return self.sendAPIRequest(url,type='DELETE')

    def createItem(self,mmsid,holid) -> APIResult:
        xml = '<item><item_data></item_data></item>'
        xml = addXmlDeclaration(xml)
        url = self.API_BIBS+str(mmsid)+'/holdings/'+str(holid)+'/items/'
        return self.sendAPIRequest(url,type='POST',xml=xml)

    def scanItem(self,mmsid,holid,itemid,
                 department=None,wo_type=None,wo_status=None,done=False,
                 library=None,circ_desk=None) -> APIResult:
        url = self.API_BIBS+str(mmsid)+'/holdings/'+str(holid)+'/items/'+str(itemid)
        url += '?op=scan'
        if library: url += '&library=' + library
        if circ_desk: url += '&circ_desk=' + circ_desk
        if department: url += '&department=' + department
        if wo_type: url += '&work_order_type=' + wo_type
        if wo_status: url += '&status=' + wo_status
        if done: url += '&done=' + 'true'
        return self.sendAPIRequest(url, type='POST', xml='dont care')

    def resolveBarcode(self,barcode) -> Tuple[bool,str,str,str,str,APIResult]:
        item_not_found = False
        mmsid = holid = itemid = None
        url = self.ALMA_API_BASE+'items?item_barcode='+urllib.parse.quote_plus(barcode)
        result = self.sendAPIRequest(url)
        if result.errs:
            s = ''.join(result.errs)
            if match := re.search('<errorCode>401689</errorCode>',s):
                item_not_found = True
        else:
            if match := re.search(r'<item\slink="(.+?)">',result.data):
                item_link = match[1]
                mmsid, holid, itemid = Item.splitLink(item_link)

        return item_not_found, mmsid, holid, itemid, result

    def listRequests(self,mmsid,holid,itemid,request_type='all_types',status='active') -> APIResult:
        url = self.API_BIBS+str(mmsid)+'/holdings/'+str(holid)+'/items/'+str(itemid)+'/requests'
        url += '?'
        url += '&1=1'
        url += '&request_type=' + request_type
        url += '&status=' + status
        return self.sendAPIRequest(url)

    def getRequest(self,mmsid,holid,itemid,requestid) -> APIResult:
        url = self.API_BIBS+str(mmsid)+'/holdings/'+str(holid)+'/items/'+str(itemid)+'/requests/'+str(requestid)
        return self.sendAPIRequest(url)

    def deleteRequest(self,mmsid,holid,itemid,requestid) -> APIResult:
        url = self.API_BIBS+str(mmsid)+'/holdings/'+str(holid)+'/items/'+str(itemid)+'/requests/'+str(requestid)+'?reason=RequestUpdated&notify_user=false'
        return self.sendAPIRequest(url,type='DELETE')

    def createSet(self,name,type,content,private,query) -> Tuple[str,APIResult]:
        errs = []
        if name is None: errs.append('parameter name not set')
        if type is None: errs.append('parameter type not set')
        if content is None: errs.append('parameter content not set')
        if private is None: errs.append('parameter private not set')
        if query is None: errs.append('parameter query not set')
        if errs:
            result = APIResult()
            result.errs = errs
            return None,result

        setid, result = self.findSetByName(name)
        if result and result.errs:
            return None,result

        if setid is not None:
            result = self.deleteSet(setid)
            if result and result.errs:
                return None,result

        url = self.API_SETS
        xml = ''
        xml += '<set>'
        xml += '<name>'+name+'</name>'
        xml += '<type>'+type+'</type>'
        xml += '<content>'+content+'</content>'
        xml += '<private>'+private+'</private>'
        xml += '<query>'+query+'</query>'
        xml += '</set>'

        setid = None
        result = self.sendAPIRequest(url,type='POST',xml=xml)
        if not result.errs:
            match=re.search(r'<id>(\d+)</id>',result.data)
            if match:
                setid = match[1]

        return setid,result

    def createItemizedBibRecordSet(self,setname='some set name',private=True) -> Tuple[str,APIResult]:
        url = self.API_SETS
        xml = ''
        xml += '<set>'
        xml += '<name>'+setname+'</name>'
        xml += '<type>ITEMIZED</type>'
        xml += '<content>BIB_MMS</content>'
        if not private:
            xml += '<private>false</private>'
        xml += '</set>'

        setid = None
        result = self.sendAPIRequest(url,type='POST',xml=xml)
        if not result.errs:
            match=re.search(r'<id>(\d+)</id>',result.data)
            if match:
                setid = match[1]

        return setid,result

    def updateSet(self,setid,xml) -> APIResult:
        url = self.API_SETS + str(setid)
        return self.sendAPIRequest(url,type='PUT',xml=xml)

    def getSet(self,setid) -> APIResult:
        url = self.API_SETS + setid
        return self.sendAPIRequest(url)

    def deleteSet(self,setid) -> APIResult:
        url = self.API_SETS + setid
        return self.sendAPIRequest(url,type='DELETE')

    def addIdToSet(self,setid,*recids) -> APIResult:
        url = self.API_SETS + setid +'?op=add_members'
        xml = ''
        xml += '<set>'
        xml += '<members>'
        xml += '<member>'
        for recid in recids:
            xml += '<id>'+str(recid)+'</id>'
        xml += '</member>'
        xml += '</members>'
        xml += '</set>'

        return self.sendAPIRequest(url,type='POST',xml=xml)

    def manageSetMembers(self,setid,op='add_members',id_type=None,*ids) -> APIResult:
        """
        URL Parameters

        Parameter	Type	    Description
        set_id	    xs:string	Unique id of the set. Mandatory.

        Querystring Parameters

        Parameter	Type	    Required	Description
        id_type	    xs:string	Optional.	The type of the identifier that is used to identify members. Optional.
            For physical items: BARCODE.
            For Bib records: SYSTEM_NUMBER, OCLC_NUMBER, ISBN, ISSN. For regular MMS-IDs no need to defined this parameter.
            For users: any type that is defined in UserIdentifierTypes Code Table
        op	        xs:string	Required	The operation to perform on the set. Mandatory. The supported operations are add_members, delete_members or replace_members.

        Body Parameters

        This method takes a Set object including list of members to add/remove. Up to 1000 members can be supplied. See doc
        Output
        This method returns a Set object. See doc

        Possible Error Codes
        Code	Message
        60107	Invalid set ID.
        60111	Invalid operation.
        60112	Invalid set type.
        60113	Input set with no members.
        60114	Input set with no member ID.
        60115	A member ID is already in the set.
        60116	A member ID is not valid for the content.
        60117	Input set member ID is not in set.
        60118	Input set member list exceeds limit.
        60119	Input set with duplicate member.
        60120	A member ID is not valid for the content and identifier.
        60176	A member ID which is represented by an id_type identifier is already in the set.
        40166410	Invalid parameter identifier type.
        """

        url = self.API_SETS + setid +'?op=op'
        if id_type is not None:
            url += '&id_type='+id_type

        xml = ''
        xml += '<set>'
        xml += '<members>'
        xml += '<member>'
        for id in ids:
            xml += '<id>'+str(id)+'</id>'
        xml += '</member>'
        xml += '</members>'
        xml += '</set>'

        return self.sendAPIRequest(url,type='POST',xml=xml)

    def findSetByName(self,setname,content_type=None,set_type=None) -> Tuple[str,APIResult]:
        setid = None

        url = self.API_SETS
        url += '?offset=0&limit=0'
        if content_type:
            url += '&content_type='+content_type
        if set_type:
            url += '&set_type='+set_type

        result = self.sendAPIRequest(url)
        if result.errs:
            return None,result
        match = re.search(r'total_record_count="(\d+)"',result.data)
        if match:
            total_cnt = int(match[1])
        else:
            result = APIResult()
            result.errs = ['cannot determine record count']
            return None,result

        cnt = 0
        offset = 0
        while cnt < total_cnt and setid is None:
            url = self.API_SETS
            url += '?offset=' + str(offset) + '&limit=100'
            if content_type:
                url += '&content_type=' + content_type
            if set_type:
                url += '&set_type=' + set_type

            result = self.sendAPIRequest(url)
            if result.errs:
                return None,result

            sets = Set.multiFromXml(result.data)
            for x in sets:
                if x.name == setname:
                    setid = x.id
            cnt += 100
            offset += 100

        return setid,None

    def fetchSetMembers(self,setid,offset=0,limit=100,max_records=999999) -> Tuple[List[SetMember],APIResult]:
        setmembers_total_record_count = 0
        offset = int(offset)
        limit = int(limit)
        max_records = int(max_records)
        if limit > 100: limit = 100

        # get no of records in set
        url = self.API_SETS
        url += str(setid)
        url += '/members?offset=0&limit=0'

        result = self.sendAPIRequest(url)
        if result.errs:
            return None,result

        match = re.search(r'<members total_record_count="(\d+)"',result.data)
        if match:
            setmembers_total_record_count = int(match.group(1))
        else:
            result = APIResult()
            result.errs = ['cannot determine set total record count']
            return None,result

        cnt = 0
        setmembers = []
        ok = True

        while offset < setmembers_total_record_count and cnt < max_records:
            url = self.API_SETS
            url += str(setid)
            url += '/members?limit=' + str(limit) + '&offset=' + str(offset)
            result = self.sendAPIRequest(url)
            if result.errs:
                return None,result

            setmembers.extend(SetMember.multiFromXml(result.data))
            offset += limit
            cnt += limit

        if len(setmembers) > max_records:
            setmembers = setmembers[0:max_records]

        return setmembers,None

    def extendSet(self,setid=None,setname=None,setid_extend_by=None,setname_extend_by=None) -> Tuple[List[SetMember],APIResult]:
        if setid is None:
            setid, result = self.findSetByName(setname)
            if result and result.errs:
                return None,result

            if setid is None:
                result = APIResult()
                result.errs.append(f"no set found for name {setname}")
                return None,result

        if setid_extend_by is None:
            setid_extend_by, result = self.findSetByName(setname_extend_by)
            if result and result.errs:
                return None,result

            if setid_extend_by is None:
                result = APIResult()
                result.errs.append(f"no set found for name {setname_extend_by}")
                return None,result


        members, result = self.fetchSetMembers(setid_extend_by)
        if result and result.errs:
            return None,result

        for member in members:
            result = self.addIdToSet(setid,member.id)
            if result and result.errs:
                return None,result

        members, result = self.fetchSetMembers(setid)
        if result and result.errs:
            return None,result

        return members, None

    def runJob(self,jobnumber,xml) -> APIResult:
        url = self.API_JOBS + jobnumber + '?op=run'
        return self.sendAPIRequest(url,type='POST',xml=xml)

    def runLinkJob(self,setid,prefix='(AT-OBV)') -> APIResult:
        url='https://api-eu.hosted.exlibrisgroup.com/almaws/v1/conf/jobs/M85?op=run'
        xml="""
        <job>
            <parameters>
                <parameter>
                    <name>contribute_nz</name>
                    <value>true</value>
                </parameter>
                <parameter>
                    <name>non_serial_match_profile</name>
                    <value>com.exlibris.repository.mms.match.OtherSystemOrStandardNumberMatchProfile</value>
                </parameter>
                <parameter>
                    <name>non_serial_match_prefix</name>
                    <value>***PREFIX***</value>
                </parameter>
                <parameter>
                    <name>serial_match_profile</name>
                    <value>com.exlibris.repository.mms.match.OtherSystemOrStandardNumberSerialMatchProfile</value>
                </parameter>
                <parameter>
                    <name>serial_match_prefix</name>
                    <value>***PREFIX***</value>
                </parameter>
                <parameter>
                    <name>ignoreResourceType</name>
                    <value>false</value>
                </parameter>
                <parameter>
                    <name>set_id</name>
                    <value>***SETID***</value>
                </parameter>
                <parameter>
                    <name>job_name</name>
                    <value>Link a set of records to the Network Zone</value>
                </parameter>
            </parameters>
        </job>
        """
        xml = xml.replace('***SETID***',setid)
        xml = xml.replace('***PREFIX***',prefix)
        return self.sendAPIRequest(url,type='POST',xml=xml)

    def runDeleteBibJob(self,setid) -> APIResult:
        url='https://api-eu.hosted.exlibrisgroup.com/almaws/v1/conf/jobs/M28?op=run'
        xml="""
        <job>
            <parameters>
                <parameter>
                    <name>HANDLE_RELATED_BIBS_isSelected</name>
                    <value>false</value>
                </parameter>
                <parameter>
                    <name>HANDLE_INVENTORY_BIBS_isSelected</name>
                    <value>false</value>
                </parameter>
                <parameter>
                    <name>set_id</name>
                    <value>***SETID***</value>
                </parameter>
                <parameter>
                    <name>job_name</name>
                    <value>Delete Bibliographic records - via API - ***SETID***</value>
                </parameter>
            </parameters>
        </job>
        """
        xml = xml.replace('***SETID***',setid)
        return self.sendAPIRequest(url,type='POST',xml=xml)

    def runChangeItemsJob(self,setid,**params) -> APIResult:
        url='https://api-eu.hosted.exlibrisgroup.com/almaws/v1/conf/jobs/M18?op=run'
        xml = ''
        xml += '<job>'
        xml += '<parameters>'
        for k,v in params.items():
            xml += f'<parameter><name>{k}_condition</name><value>Null</value></parameter>'
            xml += f'<parameter><name>{k}_selected</name><value>true</value></parameter>'
            xml += f'<parameter><name>{k}_value</name><value>{v}</value></parameter>'
        xml += f'<parameter><name>job_name</name><value>Change physical items - via API - {setid}</value></parameter>'
        xml += f'<parameter><name>set_id</name><value>{setid}</value></parameter>'
        xml += '</parameters>'
        xml += '</job>'
        return self.sendAPIRequest(url,type='POST',xml=xml)

    def getUser(self,userid,userid_type='all_unique',view='full',expand=None) -> APIResult:
        """
        user_id
            xs:string
            A unique identifier for the user

        userid_type
            xs:string
            Optional. Default: all_unique The type of identifier that is being searched. Optional.
            If this is not provided, all unique identifier types are used. The values that can be used are any of the values in the User Identifier Type code table.

        view
            xs:string
            Optional. Default: full	Special view of User object. Optional. Possible values: full - full User object will be returned. brief - only user's core information, emails, identifiers and statistics are returned. By default, the full User object will be returned.

        expand
            xs:string
            Optional. Default: none	This parameter allows for expanding on some user information. Three options are available: loans-Include the total number of loans; requests-Include the total number of requests; fees-Include the balance of fees. To have more than one option, use a comma separator.

        source_institution_code
            xs:string
            Optional. The source institution Code. Optional. When used the user_id is used to locate a copied user (linked account) based on source_link_id.
        """

        url = self.API_USERS + str(userid)
        if userid_type or view or expand:
            url += '?'
            l = []
            if userid_type: l.append('user_id_type='+urllib.parse.quote_plus(userid_type))
            if view: l.append('view='+view)
            if expand: l.append('expand='+expand)
            url += '&'.join(l)
        return self.sendAPIRequest(url)

    def createUser(self,xml) -> APIResult:
        url = self.API_USERS
        return self.sendAPIRequest(url,type='POST',xml=xml)

    def updateUser(self,userid,xml) -> APIResult:
        url = self.API_USERS+str(userid)
        return self.sendAPIRequest(url,type='PUT',xml=xml)

    def deleteUser(self,userid,userid_type='all_unique') -> APIResult:
        """
        user_id	xs:string	A unique identifier for the user

        userid_type
            Optional. Default: all_unique The type of identifier that is being searched. Optional.
            If this is not provided, all unique identifier types are used. The values that can be used are any of the values in the User Identifier Type code table.

        #401890	User with identifier X of type Y was not found.
        #401850	Failed to delete user with identifier X of type Y.
        """

        url = self.API_USERS+str(userid)
        return self.sendAPIRequest(url,type='DELETE')

    def getUserLoans(self,userid,userid_type='all_unique',
        limit=None, offset= None, order_by=None, direction=None, expand=None,
        loan_status=None) -> APIResult:
        """
        URL Parameters
        Parameter	Type	    Description
        user_id	    xs:string	A unique identifier for the user

        Querystring Parameters
        Parameter	    Type	    Required	Description
        user_id_type	xs:string	Optional.   Default: all_unique	The type of identifier that is being searched. Optional. If this is not provided, all unique identifier types are used. The values that can be used are any of the values in the User Identifier Type code table.
        limit	        xs:int	    Optional.   Default: 10	Limits the number of results. Optional. Valid values are 0-100. Default value: 10.
        offset	        xs:int	    Optional.   Default: 0	Offset of the results returned. Optional. Default value: 0, which means that the first results will be returned.
        order_by	    xs:string	Optional.   Default: id	A few sort options are available (only one can be sent): loan_date, due_date, barcode, title, author and return_date (relevant only for historical loans). A secondary sort key, id, is added to the single sort option chosen. Default sorting is by id.
        direction	    xs:string	Optional.   Default: ASC	Sorting direction: ASC/DESC. Default: ASC.
        expand	        xs:string	Optional.	Comma separated list of values for expansion of results. Possible values: 'renewable'
        loan_status	    xs:string	Optional.   Default: Active	Active or Complete loan status. Default: Active. The Complete loan status is only relevant if historic loans haven't been anonymized.

        Error Messages
        Code    Message
        401861	User with identifier X was not found.
        401890	User with identifier X of type Y was not found.
        401652	General Error: An error has occurred while processing the request.
        60258	The API Restricted profile is not valid.        """

        url = self.API_USERS + str(userid) +'/loans'
        if userid_type or loan_status or limit or offset or order_by or direction or expand or loan_status:
            url += '?'
            l = []
            if userid_type: l.append('user_id_type='+urllib.parse.quote_plus(userid_type))
            if limit: l.append('limit='+limit)
            if offset: l.append('offset='+offset)
            if order_by: l.append('order_by='+order_by)
            if direction: l.append('direction='+direction)
            if expand: l.append('expand='+expand)
            if loan_status: l.append('loan_status='+loan_status)
            url += '&'.join(l)
        return self.sendAPIRequest(url)

    def getUserFee(self,userid,feeid,userid_type='all_unique') -> APIResult:
        """
        URL Parameters
        Parameter	Type	    Description
        user_id	    xs:string	A unique identifier for the user
        fee_id      xs:string   The fine/fee identifier

        Querystring Parameters
        Parameter	    Type	    Required	Description
        user_id_type	xs:string	Optional.   Default: all_unique	The type of identifier that is being searched. Optional. If this is not provided, all unique identifier types are used. The values that can be used are any of the values in the User Identifier Type code table.

        Error Messages
        Code    Message
        402119	General error.
        401665	Fine not found.
        401651	Identifier not found.
        401666	Parameter is not valid.
        60340	The request is API Restricted by library.
        60258	The API Restricted profile is not valid.
        """
        url = self.API_USERS + str(userid) +'/fees/' + feeid
        if userid_type:
            url += '?'
            l = []
            if userid_type: l.append('user_id_type='+urllib.parse.quote_plus(userid_type))
            url += '&'.join(l)
        return self.sendAPIRequest(url)

    def getUserFees(self,userid,userid_type='all_unique',status='ACTIVE') -> APIResult:
        """
        userid	A unique identifier for the user

        userid_type
            Optional. Default: all_unique The type of identifier that is being searched. Optional.
            If this is not provided, all unique identifier types are used. The values that can be used are any of the values in the User Identifier Type code table.
        status
            Optional. Default: ACTIVE Return fees of this status only. Optional. If this is not provided,
            all active fees will be returned. The values that can be used are {ACTIVE|INDISPUTE|EXPORTED|CLOSED}.

        #402119	General error.
        #401651	Identifier not found.
        #401666	Parameter is not valid.
        """

        url = self.API_USERS + str(userid) +'/fees'
        if userid_type or status:
            url += '?'
            l = []
            if userid_type: l.append('user_id_type='+urllib.parse.quote_plus(userid_type))
            if status:l.append('status='+status)
            url += '&'.join(l)
        return self.sendAPIRequest(url)

    def payUserFee(self,userid,feeid,op='pay',userid_type='all_unique',amount=None,method=None,reason=None,
        comment=None,external_transaction_id=None) -> APIResult:
        """
        Pay user fees. Misnomer. Function can also be used to waive, dispute and restore fees.

        userid A unique identifier for the user
        feeid The fine/fee identifier
        userid_type
            Optional. Default: all_unique The type of identifier that is being searched. Optional.
            If this is not provided, all unique identifier types are used. The values that can be used are any of the values in the User Identifier Type code table.
        op
            Required. The operation to be performed on the user's specified fee. Mandatory. Options are pay, waive, dispute or restore
        amount
            Optional. The amount of the payment to be made on the user's specified fees. Relevant for op=pay,waive
        method
            Optional. The Payment method. Relevant and mandatory if op=pay. Options are CREDIT_CARD, ONLINE, or CASH
        reason
            The reason for waiving the fine/fee. Relevant and mandatory for op=waive. The value should be one of the codes from the FineFeeTransactionReason code table.
        comment
            Optional. A note that can be attached to the action. Optional.
        external_transaction_id
            Optional. An external payment system transaction ID. Relevant for op=pay

        402119	General error.
        401665	Fine not found.
        401651	Identifier not found.
        401666	Parameter is not valid.
        """

        url = self.API_USERS + str(userid) +'/fees/' + str(feeid) + '?'
        l = []
        if userid_type: l.append('user_id_type='+urllib.parse.quote_plus(userid_type))
        if op: l.append('op='+urllib.parse.quote_plus(op))
        if amount: l.append('amount='+urllib.parse.quote_plus(amount))
        if method: l.append('method='+urllib.parse.quote_plus(method))
        if reason: l.append('reason='+urllib.parse.quote_plus(reason))
        if comment: l.append('comment='+urllib.parse.quote_plus(comment))
        if external_transaction_id: l.append('external_transaction_id='+urllib.parse.quote_plus(external_transaction_id))
        url += '&'.join(l)
        return self.sendAPIRequest(url,type='POST')

    def getRDFManifestation(self,mmsid) -> APIResult:
        url = 'https://open-na.hosted.exlibrisgroup.com/alma/' + self.INSTITUTION_CODE + '/rda/entity/manifestation/' + str(mmsid) + '.rdf'
        return self.sendAPIRequest(url)

    def getRDFWork(self,workid) -> APIResult:
        url = 'https://open-na.hosted.exlibrisgroup.com/alma/' + self.INSTITUTION_CODE + '/rda/entity/work/' + str(workid)
        return self.sendAPIRequest(url)


    def getLetters(self) -> APIResult:
        """
        402119	General error.
        60344	Problem retrieving letter data.
        """
        url = self.API_CONF_LETTERS
        return self.sendAPIRequest(url)

    def getLetter(self,code) -> APIResult:
        """
        code	xs:string	The code of the letter.

        402119	    General error.
        40166411	Letter code is not valid.
        60344	    Problem retrieving letter data.
        """
        url = self.API_CONF_LETTERS + code
        return self.sendAPIRequest(url)

    def updateLetter(self,code,xml) -> APIResult:
        """
        code	xs:string	The code of the letter.

        60105	    JSON is not supported for this API.
        402119	    General error.
        40166411	Letter code or other parameter is not valid.
        60344	    Problem retrieving letter data.
        60343	    The update failed
        """
        url = self.API_CONF_LETTERS + code
        return self.sendAPIRequest(url,type='PUT',xml=xml)

    def getCodeTable(self,name,lang = None):
        """
        name    xs:string	Code table name.

        lang	xs:string	Optional.	Requested language.
        scope	xs:string	Optional. Default: Institution Code	Institution or Library code


        402119	General error.
        40166411	Param value is invalid.
        """
        url = self.API_CONF_CODE_TABLES + name
        if lang:
            url += '?lang='+lang
        return self.sendAPIRequest(url)

    
    def getAnalyticsPaths(self) -> APIResult:
        url = self.API_ANALYTICS + 'paths/'
        apikey = self.cfg[OPT_KEYS][OPT_KEYS_ANALYTICS]

        return self.sendAPIRequest(url,apikey=apikey)

    def getAnalyticsReport(self,path=None,filter=None,limit=1000,col_names=True,token=None) -> Tuple[List[str],APIResult]:
        s = ''
        t = ''
        rows = []
        apikey = self.cfg[OPT_KEYS][OPT_KEYS_ANALYTICS]
        finished = False
        urlparams = {}
        if path: urlparams['path'] = urllib.parse.quote_plus(path)
        if filter: urlparams['filter'] = filter
        if limit: urlparams['limit'] = str(limit)
        if col_names is not None: urlparams['col_names'] = str(col_names).lower()
        if token: urlparams['token'] = token

        while urlparams and not finished:
            url = self.API_ANALYTICS + 'reports/?'
            l = [x + '=' + y for x,y in urlparams.items()]
            url += '&'.join(l)
            result = self.sendAPIRequest(url,apikey=apikey)
            if result.errs:
                return None,result

            match = re.search(r'<ResumptionToken>(.+?)</ResumptionToken>',result.data)
            if match:
                token = match.group(1)
            else:
                token = None

            match = re.search(r'<IsFinished>(.+?)</IsFinished>',result.data)
            if match:
                finished = True if match.group(1) == 'true' else False
            else:
                finished = True

            if token:
                urlparams['token'] = token
            else:
                del urlparams['token']

            if not t and col_names:
                match = re.search('<xsd:sequence>(.+?)</xsd:sequence>',result.data,re.DOTALL)
                t += '<xsd:sequence>' + match[1] + '</xsd:sequence>'

            rows = re.findall(r'<Row>(.+?)</Row>',result.data,re.DOTALL)
            l = []
            for row in rows:
                cols = re.finditer(r'(<Column\d{1,2}>)(.+?)(</Column\d{1,2}>)',row,re.DOTALL)
                for col in cols:
                    l.append(col.group(1))
                    l.append(col.group(2))
                    l.append(col.group(3))
                s += '<row>' + ''.join(l) + '</row>'

        s = '<rows>' + s + '</rows>'
        if t:
            s = t + s

        return s,None


    # inflexible, just for test purposes
    def makeAnalyticsFilter(self,operator=None,column=None,value=None):
        filter = """
        <sawx:expr xsi:type="sawx:list" op="{}"
              xmlns:saw="com.siebel.analytics.web/report/v1.1"
              xmlns:sawx="com.siebel.analytics.web/expression/v1.1"
              xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
              xmlns:xsd="http://www.w3.org/2001/XMLSchema"
        >
        <sawx:expr xsi:type="sawx:sqlExpression">{}</sawx:expr>
        <sawx:expr xsi:type="xsd:string">{}</sawx:expr>
        </sawx:expr>
        """.format(operator,column,value)

        filter = textwrap.dedent(filter)
        filter = ' '.join(filter.splitlines())

        return filter

    def sendSRURequest(self,**params) -> APIResult:
        SRU_ENDPOINT = "https://obv-at-ubtuw.alma.exlibrisgroup.com/view/sru/43ACC_NETWORK?version=1.2&operation=searchRetrieve&query="
        errs = []
        timeout = int(self.cfg[OPT_OPTIONS][OPT_OPTIONS_TIMEOUT])

        l = []
        url = SRU_ENDPOINT
        for k,v in params.items():
            l.append(k + '=' + urllib.parse.quote_plus(v))
        url += '&'.join(l)

        try:
            result = APIResult()
            r = requests.request('GET',url,timeout=(timeout,timeout))

            status_code = r.status_code
            data = r.text
            logger.debug(f"status={r.status_code} response={r.text}")

        except Exception as e:
            errs.append('Alma SRU error')
            errs.append(str(e))
            errs.append(traceback.format_exc())
            logger.error("exception={}".format(str(e)))
            logger.error("stacktrace={}".format(traceback.format_exc()))
            if r:
                errs.append(f"status={r.status_code} response={r.text}")
                logger.error(f"status={r.status_code} response={r.text}")

        result.data = data
        result.errs = errs
        result.error_code = None
        result.error_message = None
        result.http_status = status_code

        return result

    def getRequestedResources(self,library,circ_desk,**params) -> APIResult:
        url = self.API_TASK_LISTS + 'requested-resources'
        url += '?library=' + library
        url += '&circ_desk=' + circ_desk
        l = []
        for k,v in params.items():
            l.append(k + '=' + urllib.parse.quote_plus(v))
        if l:
            url += '&'
            url += '&'.join(l)

        return self.sendAPIRequest(url)



