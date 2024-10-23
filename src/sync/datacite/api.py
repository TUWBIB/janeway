import os
import sys
import requests
import re
import traceback
import json
from requests.auth import HTTPBasicAuth
from requests.exceptions import ConnectTimeout,ReadTimeout
from pathlib import Path
import base64


class API():
    def __init__(self,obj_cfg=None,file_cfg=None,json_str=None):
        self.options = {}
        self.login = {}
        self.journals = {}
        self.last_headers=None
        self.last_status=None
        self.last_response=None
        self.last_timeout=None            

        if obj_cfg:
            data = obj_cfg
        elif json_str:
            data = json.loads(json_str)
        else:

            if file_cfg is None:
                file_cfg = Path(os.path.join(os.path.dirname(__file__),'api.json'))
            else:
                file_cfg = Path(file_cfg)

            if not file_cfg.exists() or not file_cfg.is_file():
                raise Exception(f'DataciteApi config file does not exist: {file_cfg}')

            with open(file_cfg,'r',encoding='utf-8') as file:
                try:
                    data = json.load(file)
                except Exception as e:
                    raise Exception(f'DataciteApi config file has errors: {e}')

        if not 'options' in data.keys():
            raise Exception("DataciteApi config file: 'options' expected")

        if not 'login' in data.keys():
            raise Exception("DataciteApi config file: 'login' expected")
        
        if not 'journals' in data.keys():
            raise Exception("DataciteApi config file: 'journals' expected")

        if not 'protocol' in data['options'].keys():
            raise Exception("DataciteApi config file: 'options.id_protocl' expected")

        if not 'id_offset' in data['options'].keys():
            raise Exception("DataciteApi config file: 'options.id_offset' expected")

        if not 'conn_timeout' in data['options'].keys():
            conn_timeout = 2
        
        if not 'read_timeout' in data['options'].keys():
            read_timeout = 5

        if not 'endpoint' in data['login'].keys():
            raise Exception("DataciteApi config file: 'login.endpoint' expected")

        if not 'user' in data['login'].keys():
            raise Exception("DataciteApi config file: 'login.user' expected")

        if not 'password' in data['login'].keys():
            raise Exception("DataciteApi config file: 'login.password' expected")
                    

        self.options = data['options']
        self.login = data['login']
        self.journals = data['journals']
#            for k,v in self.options.items():
#    	        print (str(k)+': '+str(v))
#    
#            for k,v in self.login.items():
#    	        print (str(k)+': '+str(v))
#    
#            for k,v in self.journals.items():
#                print (k)
#                for k1,v1 in self.journals[k].items():
#    	            print ('   '+str(k1)+': '+str(v1))


    def doiConformsToCurrentConfiguration(self,journal_code,doi):
        prefix = self.journals[journal_code]['prefix']
        namespace_separator = self.journals[journal_code]['namespace_separator']
        pattern = prefix+'/'+namespace_separator+r'\.\d{4}\.\d{3,4}'

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
        try:
            response = requests.get(url,
                            auth=HTTPBasicAuth(self.login['user'],self.login['password']),
                            )
            
            if response.status_code != 200:
                status = "error"
            content=response.text

        except ConnectTimeout as e:
            status = "error"
            content = (''.join(['connect timeout: ',str(e)]))
        except ReadTimeout as e:
            status = "error"
            content = (''.join(['read timeout: ',str(e)]))
        except Exception as e:
            status = "error"
            content = (''.join(['general exception: ',str(e)]))

        return (status,content)

    def updateMetadata(self,doi,xml):
        url = self.login['endpoint']
        url += 'metadata/'
        url += doi

        status = 'success'
        try:
            response = requests.put(url,
                            auth=HTTPBasicAuth(self.login['user'],self.login['password']),
                            headers={'Content-Type': 'application/xml;charset=UTF-8'},
                            data=xml.encode('utf-8'))
            
            if response.status_code != 201:
                status = "error"
                content=response.text;    
            else:
                match = re.search(r'OK \((.+)\)',response.text)
                if match is None:
                    status = "error"
                    content = "can't decode doi from response"
                else:
                    content = match.group(1)

        except ConnectTimeout as e:
            status = "error"
            content = (''.join(['connect timeout: ',str(e)]))
        except ReadTimeout as e:
            status = "error"
            content = (''.join(['read timeout: ',str(e)]))
        except Exception as e:
            status = "error"
            content = (''.join(['general exception: ',str(e)]))

        return (status,content)

    def deleteDOI(self,doi):
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
        
            if response.status_code != 200:
                status = "error"
                content = response.text;
                content = str(response.status_code) + "-" + response.text
            else:
                content = ''
        except ConnectTimeout as e:
            status = "error"
            content = (''.join(['connect timeout: ',str(e)]))
        except ReadTimeout as e:
            status = "error"
            content = (''.join(['read timeout: ',str(e)]))
        except Exception as e:
            status = "error"
            content = (''.join(['general exception: ',str(e)]))

        return (status,content)


    def getURL(self,doi):
        url = self.login['endpoint']
        url += 'doi/'
        url += doi
        
        status = 'success'
        try:
            response = requests.get(url,
                            auth=HTTPBasicAuth(self.login['user'],self.login['password']),
                            )

            content=response.text
            if response.status_code != 200:
                status = "error"
                if response.status_code == 400:
                    content = "Not found"

        except ConnectTimeout as e:
            status = "error"
            content = (''.join(['connect timeout: ',str(e)]))
        except ReadTimeout as e:
            status = "error"
            content = (''.join(['read timeout: ',str(e)]))
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
        try:
            response = requests.put(url,
                            auth=HTTPBasicAuth(self.login['user'],self.login['password']),
                            headers={'Content-Type': 'text/plain;charset=UTF-8'},
                            data=data)

            if response.status_code != 201:
                status = "error"
                content=response.text;    
            else:
                content=''

        except ConnectTimeout as e:
            status = "error"
            content = (''.join(['connect timeout: ',str(e)]))
        except ReadTimeout as e:
            status = "error"
            content = (''.join(['read timeout: ',str(e)]))
        except Exception as e:
            status = "error"
            content = (''.join(['general exception: ',str(e)]))
        
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

if __name__ == '__main__':
    try:
        api=API()
    except Exception as e:
        print (traceback.format_exc())
