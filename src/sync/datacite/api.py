import os
import sys
import requests
import re
import traceback
from requests.auth import HTTPBasicAuth
from requests.exceptions import ConnectTimeout,ReadTimeout
from pathlib import Path
import base64

class API:

    instance = None

    @classmethod
    def getInstance(cls):
        if cls.instance is None:
            cls.instance = API()
        return cls.instance


    def __init__(self):
        self.login={}
        self.options={}
        self.journals={}
        self.last_headers=None
        self.last_status=None
        self.last_response=None
        self.last_timeout=None

        file_cfg=Path(os.path.join(os.path.dirname(__file__),'api.cfg'))        
        if ((not file_cfg.exists()) or (not file_cfg.is_file())):
            raise Exception("DataciteApi config file doesn't exist: "+str(file_cfg))

        options_section=0
        login_section=0
        journal_section=0
        journal_code=None

        with open(str(file_cfg),'r',encoding='utf-8') as file:
            lines=file.readlines()
            for line in lines:
                line=line.strip();
                match=re.match('^#$',line)
                if match:
                    continue
                if line=='<LOGIN>':
                    login_section=1
                    options_section=0
                    journal_section=0
                    journal_code=None
                    continue
                if line=='<OPTIONS>':
                    login_section=0
                    options_section=1
                    journal_section=0
                    journal_code=None
                    continue

                match=re.match('^<JOURNAL\s(.+?)>$',line)
                if match:
                    login_section=0
                    options_section=0
                    journal_section=1
                    journal_code=match[1]
                    self.journals[journal_code]={}
                    continue

                match=re.match('.+=.+',line)
                if not match:
                    raise Exception("DataciteApi config file contains invalid line: "+line)
                (key,val)=line.split('=')
                if options_section:
                    if key not in ('error_threshold','error_die','conn_timeout','read_timeout','id_offset','protocol'):
                        raise Exception('DataciteAPI config file, invalid option: '+key)
                    self.options[key]=val

                elif login_section:
                    if key not in ('endpoint','user','password'):
                        raise Exception('DataciteAPI config file, invalid option: '+key)
                    self.login[key]=val
                
                elif journal_section:
                    if key not in ('prefix','namespace_separator','start'):
                        raise Exception('DataciteAPI config file, invalid option: '+key)
                    self.journals[journal_code][key]=val
                    

#        for k,v in self.options.items():
#	        print (k+': '+v)
#
#        for k,v in self.login.items():
#            print (k+': '+v)
#
#        for k,v in self.journals.items():
#            print (k)
#            for k1,v1 in self.journals[k].items():
#                print ("   "+k1+': '+v1)

    def doiConformsToCurrentConfiguration(self,journal_code,doi):
        prefix = self.journals[journal_code]['prefix']
        namespace_separator = self.journals[journal_code]['namespace_separator']
        pattern = prefix+'/'+namespace_separator+r'\.'+r'\d{4}'+r'\.'+r'\d{4}'
        match = re.match(pattern,doi)
        if not match:
            return False
        else:
            return True


    def getMetadata(self,doi):
        url = self.login['endpoint']
        url += 'metadata/'
        url += doi

        status = 'success'
        response = requests.get(url,
                        auth=HTTPBasicAuth(self.login['user'],self.login['password']),
                        )
        
        if response.status_code != 200:
            status = "error"
        content=response.text;
        return (status,content)

    def updateMetadata(self,doi,xml):
        url = self.login['endpoint']
        url += 'metadata/'
        url += doi

        status = 'success'
        response = requests.put(url,
                        auth=HTTPBasicAuth(self.login['user'],self.login['password']),
                        headers={'Content-Type': 'application/xml;charset=UTF-8'},
                        data=xml.encode('utf-8'))
        
        if response.status_code != 201:
            status = "error"
            content=response.text;    
        else:
            match = re.search('OK \((.+)\)',response.text)
            if match is None:
                status = "error"
                content = "can't decode doi from response"
            else:
                content = match.group(1)
        
        return (status,content)

    def deleteDOI(self,doi):
        print ("delete DOI")
        url = self.login['endpoint']
        url += 'doi/'
        url += doi

        status = "success"
        try:
            response = requests.delete(url,
                        auth=HTTPBasicAuth(self.login['user'],self.login['password']),
                        headers={'Content-Type': 'text/plain;charset=UTF-8'},
                        timeout=(int(self.options['conn_timeout']),int(self.options['read_timeout'])),                        
                        )
        
            if response.status_code != 204:
                status = "error"
                content = response.text;
                content = str(response.status_code) + "-" + response.text
            else:
                content = ''
        except ConnectTimeout as e:
            status = "error"
            content = (''.join(['connect timeout: ',str(e)]))
#        except ReadTimeout as e:
#            status = "error"
#            content = (''.join(['read timeout: ',str(e)]))

# no response from Datacite API when deletions are successful
# assume everything's ok
        except ReadTimeout as e:
            status = "success"
            content = ''
        except Exception as e:
            status = "error"
            content = (''.join(['general exception: ',str(e)]))

        return (status,content)

    def registerURL(self,doi,article_url):
        url = self.login['endpoint']
        url += 'doi/'
        url += doi
        data='doi='+doi+'\n'+'url='+article_url
        status = 'success'
        response = requests.put(url,
                        auth=HTTPBasicAuth(self.login['user'],self.login['password']),
                        headers={'Content-Type': 'text/plain;charset=UTF-8'},
                        data=data)

        if response.status_code != 201:
            status = "error"
            content=response.text;    
        else:
            content=''
        
        return (status,content)

#    def listDOIs(self):
#        req_url = self.login['endpoint']+'doi'
#        print (req_url)
#        response = requests.get(req_url,
#                        auth=HTTPBasicAuth(self.login['user'],self.login['password']),
#                        )
#        if response.status_code != 201: 
#            print (str(response.status_code))
#        content=response.text
#        print (content)

