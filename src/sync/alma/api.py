import os
import sys
import re
import json
import traceback
import requests
import lxml
from lxml import etree
from pathlib import Path

class API:
    instance = None
    def __init__(self):
        if not API.instance:
            API.instance = API.__API()

    def __getattr__(self, name):
        return getattr(self.instance, name)

    class __API:

        ALMA_API_BASE='https://api-eu.hosted.exlibrisgroup.com';
        API_CONF='/almaws/v1/conf/';
        RESPONSE_FORMAT='application/xml'

        error_count=0

        def __init__(self):
            self.api_key=None
            self.last_headers=None
            self.last_status=None
            self.last_response=None
            self.last_timeout=None
            self.last_err=None

            file_cfg = Path(os.path.join(os.path.dirname(__file__),'api.json'))
            if ((not file_cfg.exists()) or (not file_cfg.is_file())):
                raise Exception("AlmaApi config file doesn't exist: "+str(file_cfg))

            with open(file_cfg,'r',encoding='utf-8') as file:
                try:
                    data = json.load(file)
                except Exception as e:
                    raise Exception("AlmaApi config file has errors: "+str(e))

            if not 'options' in data.keys():
                raise Exception("AlmaApi config file: 'options' expected")

            if not 'keys' in data.keys():
                raise Exception("AlmaApi config file: 'keys' expected")



            self.options = data['options']
            self.api_keys = data['keys']

            if not 'error_threshold' in self.options.keys():
                self.options['error_threshold']=0

            if not 'timeout' in self.options.keys():
                self.options['timeout']=0

            if 'target' not in self.options.keys():
                raise Exception("AlmaApi config file error: option 'target' needs to be set")

            target = self.options['target']
            if target not in self.api_keys.keys():
                raise Exception("AlmaApi config file error: no api key for 'target' " + target + "set")
        
            self.setAPITarget(target)

        def setAPITarget(self,key):
            if key in self.api_keys:
                self.api_key=self.api_keys[key]
            else:
                raise Exception('AlmaApi, invalid api target: '+key)


#        def sendAPIRequest(self,url,type='GET',xml=None,json=None):
#
#            headers={'Authorization' : self.api_key,
#                    'Accept' : self.RESPONSE_FORMAT,
#                    }
#
#            cnt_errors=0
#            while cnt_errors<=int(self.options['error_threshold']):
#                self.last_err=None
#                timeout=False
#
#                try:
#                    if type=='GET' or type=='DELETE':
#                        r=requests.request(type,url,headers=headers,timeout=int(self.options['timeout']))
#                    elif type=='PUT' or type=='POST':
#                        if xml is not None:
#                            headers['Content-Type']='application/xml; charset=utf-8'
#                            r=requests.request(type,url,headers=headers,timeout=int(self.options['timeout']),data=xml.encode('utf-8'))
#                        elif json is not None:
#                            r=requests.request(type,url,headers=headers,timeout=int(self.options['timeout']),json=json)                            
#                        else:
#                            raise ValueError("Request type {}, but neither xml nor json data set".format(type))    
#                    else:
#                        raise NameError("Invalid request type {}".format(type))
#
#                except TimeoutError:
#                    self.last_timeout=True
#                else:
#                    self.last_timeout=False
#                    self.last_headers=r.headers
#                    self.last_status=r.status_code
#                    self.last_response=r.text
#                    self.last_err=re.match('errorsExist',r.text)
#                if not r or self.last_err is not None or self.last_timeout:
#                    cnt_errors+=1
#                else:
#                    break
#            if cnt_errors>int(self.options['error_threshold']):
#                l=[]
#                if self.last_err:
#                    l.append(self.last_err)
#                if self.last_timeout:
#                    l.append(str(self.last_timeout))
#                l.append(str(self.last_status))
#                l.append(self.last_response)
#                msg = ''.join(l)
#
#                raise Exception(msg)
#            return self.last_response


        def sendAPIRequest(self,url,type='GET',xml=None,json=None):
            errs = []
            r = None
            data = None

            headers = {'Authorization' : self.api_key,
                        'Accept' : self.RESPONSE_FORMAT,
                      }

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

            except Exception as e:
                 errs.append('Alma API error')
                 errs.append(str(e))
                 if r:
                    errs.append(str(r.status_code))
                    errs.append(r.text)

            if not errs:
                match = re.search('errorsExist',r.text)
                if match:
                     errs.append('Alma API error')
                     errs.append(r.text)

            if r:
                data = r.text

            return (data,errs)

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
                (response,errs)=self.sendAPIRequest(url)
                if (errs):
                    ok=False
                else:
                    SetMember.addMembersFromXml(setmembers,response)
                    offset+=limit
                    cnt+=limit

            return setmembers if ok else None

        def createBibRecord(self,xml,unsuppress=True):
            url = 'https://api-eu.hosted.exlibrisgroup.com/almaws/v1/bibs/'
            xml, errs = self.sendAPIRequest(url,type='POST',xml=xml)

            if errs:
                return (xml,errs)

            if unsuppress:
                if match := re.search('<mms_id>(\d+)</mms_id>',xml):
                    mmsid = str(match[1])
                    xml = re.sub('<suppress_from_publishing>true</suppress_from_publishing>','<suppress_from_publishing>false</suppress_from_publishing>',xml)
                    (xml,errs) = self.updateBibRecord(xml,mmsid)

            return (xml,errs)

        def updateBibRecord(self,xml,mmsid):
            url='https://api-eu.hosted.exlibrisgroup.com/almaws/v1/bibs/'+str(mmsid)
            return self.sendAPIRequest(url,type='PUT',xml=xml)


        def getBibRecord(self,mmsid):
            url='https://api-eu.hosted.exlibrisgroup.com/almaws/v1/bibs/'+str(mmsid)
            return self.sendAPIRequest(url)

        def createItemizedBibRecordSet(self,setname='JW created set'):
            url = 'https://api-eu.hosted.exlibrisgroup.com/almaws/v1/conf/sets/'
            xml = ''
            xml += '<set>'
            xml += '<name>'+setname+'</name>'
            xml += '<type>ITEMIZED</type>'
            xml += '<content>BIB_MMS</content>'
            xml += '</set>'

            setid = None
            (response,errs)=self.sendAPIRequest(url,type='POST',xml=xml)
            if not errs:
                match=re.search('<id>(\d+)</id>',response)
                if match:
                    setid = match[1]

            return setid,errs

        def deleteSet(self,setid):
            url = 'https://api-eu.hosted.exlibrisgroup.com/almaws/v1/conf/sets/'+setid
            return self.sendAPIRequest(url,type='DELETE')

        def addIdToSet(self,setid,recid):
            url = 'https://api-eu.hosted.exlibrisgroup.com/almaws/v1/conf/sets/'+setid+'?op=add_members'
            xml = ''
            xml += '<set>'
            xml += '<members>'
            xml += '<member>'
            xml += '<id>'+str(recid)+'</id>'
            xml += '</member>'
            xml += '</members>'
            xml += '</set>'
            print (xml)

            return self.sendAPIRequest(url,type='POST',xml=xml)

        def runLinkJob(self,setid):
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
                        <value/>
                    </parameter>
                    <parameter>
                        <name>serial_match_profile</name>
                        <value>com.exlibris.repository.mms.match.OtherSystemOrStandardNumberSerialMatchProfile</value>
                    </parameter>
                    <parameter>
                        <name>serial_match_prefix</name>
                        <value/>
                    </parameter>
                    <parameter>
                        <name>ignoreResourceType</name>
                        <value>false</value>
                    </parameter>
                    <parameter>
                        <name>set_id</name>
            """
            xml+='<value>'+str(setid)+'</value>'
            xml+="""
                    </parameter>
                    <parameter>
                        <name>job_name</name>
                        <value>Link a set of records to the Network Zone</value>
                    </parameter>
                </parameters>
            </job>
            """

            print (xml)

            return self.sendAPIRequest(url,type='POST',xml=xml)

        def stripXmlDeclaration(self,xml):
            # strip encoding declaration
            # etree complains otherwise
            match=re.match(r'<\?xml version="1.0" encoding="UTF-8" standalone="yes"\?>(.+)',xml)
            if match:
                return match.group(1)
            else:
                return xml

        def addXmlDeclaration(self,xml):
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

