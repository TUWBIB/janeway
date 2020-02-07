import os
import sys
import re
import traceback
import requests
import lxml
from lxml import etree
from pathlib import Path

class API:
    ALMA_API_BASE='https://api-eu.hosted.exlibrisgroup.com';
    API_CONF='/almaws/v1/conf/';
    RESPONSE_FORMAT='application/xml'

    error_count=0

    def __init__(self):
        self.api_key=None
        self.api_keys={}
        self.options={}
        self.last_headers=None
        self.last_status=None
        self.last_response=None
        self.last_timeout=None

        file_cfg=Path(os.path.join(os.path.dirname(__file__),'api.cfg'))        
        if ((not file_cfg.exists()) or (not file_cfg.is_file())):
            print ("err")
            raise Exception("AlmaApi config file doesn't exist: "+str(file_cfg))

        options_section=0
        keys_section=0

        with open(str(file_cfg),'r',encoding='utf-8') as file:
            lines=file.readlines()
            for line in lines:
                line=line.strip();
                match=re.match('^#$',line)
                if match:
                    continue
                if line=='<KEYS>':
                    keys_section=1
                    options_section=0
                elif line=='<OPTIONS>':
                    keys_section=0
                    options_section=1
                else:
                    match=re.match('.+=.+',line)
                    if not match:
                        raise Exception("AlmaApi config file conatins invalid line: "+line)
                    (key,val)=line.split('=')
                    if options_section:
                        if key not in ('error_threshold','error_die','timeout'):
                            raise Exception('AlmaApi config file, invalid option: '+key)
                        self.options[key]=val

                    elif keys_section:
                        match=re.match('^apikey',val)
                        if not match:
                            raise Exception('AlmaApi config file, invalid api-key: '+val)
                        self.api_keys[key]=val


        for k,v in self.options.items():
	        print (k+': '+v)

        for k,v in self.api_keys.items():
            print (k+': '+v)


   
    
    def setAPITarget(self,key):
        if key in self.api_keys:
            self.api_key=self.api_keys[key]
        else:
            raise Exception('AlmaApi, invalid api target: '+key)



    def sendAPIRequest(self,url,type='GET',xml=None,json=None):

        headers={'Authorization' : self.api_key,
                 'Accept' : self.RESPONSE_FORMAT,
                }

        cnt_errors=0
        while cnt_errors<=int(self.options['error_threshold']):
            err=None
            timeout=False

            try:
                if type=='GET' or type=='DELETE':
                    r=requests.request(type,url,headers=headers,timeout=int(self.options['timeout']))
                elif type=='PUT' or type=='POST':
                    if xml is not None:
                        headers['Content-Type']='application/xml; charset=utf-8'
                        r=requests.request(type,url,headers=headers,timeout=int(self.options['timeout']),data=xml.encode('utf-8'))
                    elif json is not None:
                        r=requests.request(type,url,headers=headers,timeout=int(self.options['timeout']),json=json)                            
                    else:
                        raise ValueError("Request type {}, but neither xml nor json data set".format(type))    
                else:
                    raise NameError("Invalid request type {}".format(type))

            except TimeoutError:
                self.last_timeout=True
            else:
                self.last_timeout=False
                self.last_headers=r.headers
                self.last_status=r.status_code
                self.last_response=r.text
                err=re.match('errorsExist',r.text)
            print (str(r.status_code))
            print (r.headers)
            print (r.text)
            if not r or err is not None or self.last_timeout:
                cnt_errors+=1
#                print ("cnt_errors "+str(cnt_errors))
            else:
                break
        if cnt_errors>int(self.options['error_threshold']):
            raise Exception('fatal api error')
        return self.last_response

    def fetchSetMembers(self,set_id,offset,limit,max_records):
        url=API.ALMA_API_BASE+API.API_CONF+'sets/'+str(set_id)+'/members?limit=0&offset=0'
        reponse=None
        setmembers_total_record_count=0
        offset=int(offset)
        limit=int(limit)
        max_records=int(max_records)
        try:
	        response=self.sendAPIRequest(url)
        except Exception as e:
            print (traceback.format_exc())
            return None

        match=re.search(r'<members total_record_count=\"(\d+)\"\/>',response)
        if match:
            setmembers_total_record_count=int(match.group(1))
            print ('setmembers total_record_count '+str(setmembers_total_record_count))
        else:
            print ('fatal setmembers total_record_count '+str(setmembers_total_record_count))
            return None

        cnt=0
        setmembers=[]
        ok=True

#        print ('max_records='+str(max_records)+' ; offset='+str(offset)+' ; limit='+str(limit)+' cnt='+str(cnt))
        while ((ok) and (offset<setmembers_total_record_count) and (cnt<max_records)):
 #           print ('max_records='+str(max_records)+' ; offset='+str(offset)+' ; limit='+str(limit)+' cnt='+str(cnt))
        
            url=API.ALMA_API_BASE+API.API_CONF+'sets/'+str(set_id)+'/members?limit='+str(limit)+'&offset='+str(offset)
  #          print (url)
            try:            
                response=self.sendAPIRequest(url);
            except Exception as e:
                print (traceback.format_exc())
                ok=False
            else:
                SetMember.addMembersFromXml(setmembers,response)
                offset+=limit
                cnt+=limit

        return setmembers if ok else None


    def createBibRecord(self,xml):
        url='https://api-eu.hosted.exlibrisgroup.com/almaws/v1/bibs/'
        self.sendAPIRequest(url,type='POST',xml=xml)


    @staticmethod
    def stripXmlDeclaration(xml):
        # strip encoding declaration
        # etree complains otherwise
        match=re.match(r'<\?xml version="1.0" encoding="UTF-8" standalone="yes"\?>(.+)',xml)
        if match:
            return match.group(1)
        else:
            return xml

    @staticmethod
    def addXmlDeclaration(xml):
        match=re.match(r'^<\?xml version="1.0" encoding="UTF-8" standalone="yes"\?>',xml)
        if match:
            return xml
        else:
            return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'+xml


class SetMember:
    def __init(self):
        self.link=None
        self.id=None
        self.desc=None
    
    def dump(self):
        print('setmember: link='+self.link+' ; id='+self.id+' ; desc='+self.desc)

    @classmethod   
    def addMembersFromXml(cls,setmembers,xml):
        root=etree.fromstring(API.stripXmlDeclaration(xml))
        nl_member=root.findall('.//member')
        for node_member in nl_member:
            setmember=SetMember()
            setmember.link=node_member.attrib['link']
            setmember.id=node_member.find('id').text
            setmember.desc=node_member.find('description').text
            setmembers.append(setmember)

if __name__ == '__main__':
    try:
        api=API()
        api.setAPITarget('sandbox')
    except Exception as e:
        print (traceback.format_exc())


    url='https://api-eu.hosted.exlibrisgroup.com/almaws/v1/bibs/997630548203336'
    (err,response)=api.sendAPIRequest(url)
    if err!=0:
        print ("api call failed")
    else:
        print ("success")
        print (response)

