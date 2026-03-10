from __future__ import annotations

import re
import traceback
import logging
import datetime
from lxml import etree
from xml.sax.saxutils import escape, unescape
from html import unescape as html_unescape
from typing import List,Tuple,Dict


from .common import \
    DC_FIELD_COVERAGE, DC_FIELD_CREATOR, DC_FIELD_DATE, DC_FIELD_DESCRIPTION, DC_FIELD_FORMAT, DC_FIELD_IDENTIFIER, DC_FIELD_LANGUAGE, DC_FIELD_PUBLISHER, DC_FIELD_RIGHTS, DC_FIELD_SOURCE, DC_FIELD_SUBJECT, DC_FIELD_TITLE, DC_FIELD_TYPE, DC_FIELDS
from .common import \
    MARC21_DC_MAP_GENERIC, MARC21_DC_MAP_HSS, MARC21_DC_MAP_OES_JFM
from .tasks_models import Coverage, CoverageResult

KEY_VOLUME_YEAR_ISSUE = 'volume_year_issue' 
KEY_VOLUME_YEAR = 'volume_year'
KEY_YEAR = 'year'
MAP_PATTERN: Dict[str,re.Pattern] = {}
MAP_PATTERN[KEY_VOLUME_YEAR_ISSUE] = re.compile('^(?:\d+=)?(\d+(?:/\d+)?)\.(\d{4}(?:/\d{2})?(?:\(\d{4}\))?),(\d+(?:\-\d+)?(?:,\d+(?:\-\d+)?)*)$')
MAP_PATTERN[KEY_VOLUME_YEAR] = re.compile('^(?:\d+=)?(\d+(?:/\d+)?)\.(\d{4}(?:/(?:\d{2}|\d{4}))?(?:\(\d{4}\))?)$')
MAP_PATTERN[KEY_YEAR] = re.compile('^(?:(?:WS|SS)\s)?(\d{4}(?:/\d{2})?(?:\(\d{4}\))?)$')
PATTERN_DECODE_REPORTING_YEAR = re.compile('\d{4}(?:/(?:\d{4}|\d{2}))?(\(\d{4}\))')
PATTERN_IGNORE_HOLDING_ISSUES = re.compile('^((?:\d+\.)?(?:\d{4})(?:/(?:\d{4}|\d{2}))?(?:\(\d{4}\))?),')

class MarcRecord:
    leader: str
    controlfields: List[ControlField]
    datafields: List[DataField]

    def __init__(self):
        self.leader = None
        self.controlfields = []
        self.datafields = []

    def __str__(self):
        return 'leader: {};'.format(self.leader)

    def parseNode(self,node,flag_html_unescape=False):
        self.parse(etree.tostring(node, encoding='unicode'),flag_html_unescape)

    def parse(self,xml: str,flag_html_unescape=False):
        # hack for simplicity, when using OAI publishing a default namespace is provided
        # for each MARC record; get rid of it
        xml = xml.replace(' xmlns="http://www.loc.gov/MARC21/slim"','')

        root = etree.fromstring(xml)
        if root.tag == 'record':
            record = root
        else:
            record = root.findall('record')[0]
        self.controlfields = []
        self.datafields = []
        nl_leader = record.findall('leader')
        if nl_leader:
            self.leader = nl_leader[0].text
        nl_cfield = record.findall('controlfield')
        for node_cfield in nl_cfield:
            cfield = ControlField()
            cfield.value = node_cfield.text
            cfield.tag = node_cfield.attrib['tag']
            self.controlfields.append(cfield)
        nl_dfield = record.findall('datafield')
        for node_dfield in nl_dfield:
            dfield = DataField()
            dfield.value = node_dfield.text
            dfield.tag = node_dfield.attrib['tag']
            dfield.ind1 = node_dfield.attrib['ind1']
            dfield.ind2 = node_dfield.attrib['ind2']
            dfield.subfields=[]
            self.datafields.append(dfield)
            nl_subfield = node_dfield.findall('subfield')
            for node_subfield in nl_subfield:
                if node_subfield.text and node_subfield.text != '':
                    subfield = SubField()
                    subfield.value = unescape(node_subfield.text)
                    if flag_html_unescape:
                        subfield.value = html_unescape(subfield.value)
                    subfield.value = subfield.value.strip()
                    subfield.code = node_subfield.attrib['code']
                    dfield.subfields.append(subfield)
    
    @classmethod
    def parseMultiple(cls,xml,flag_html_unescape=False) -> List[MarcRecord]:
        mr_list = []
        xml = xml.replace(' xmlns="http://www.loc.gov/zing/srw/"','')
        xml = xml.replace(' xmlns="http://www.loc.gov/MARC21/slim"','')
 
        root = etree.fromstring(xml)
        if root.tag == 'searchRetrieveResponse':
            nl = root.findall('records/record/recordData/record')
        else:
            nl = root.findall('record')
        for record in nl:
            mr = MarcRecord()
            mr.controlfields = []
            mr.datafields = []
            mr.leader = record.findall('leader')[0].text
            nl_cfield = record.findall('controlfield')
            for node_cfield in nl_cfield:
                cfield = ControlField()
                cfield.value = node_cfield.text
                cfield.tag = node_cfield.attrib['tag']
                mr.controlfields.append(cfield)
            nl_dfield = record.findall('datafield')
            for node_dfield in nl_dfield:
                dfield = DataField()
                dfield.value = node_dfield.text
                dfield.tag = node_dfield.attrib['tag']
                dfield.ind1 = node_dfield.attrib['ind1']
                dfield.ind2 = node_dfield.attrib['ind2']
                dfield.subfields=[]
                mr.datafields.append(dfield)
                nl_subfield = node_dfield.findall('subfield')
                for node_subfield in nl_subfield:
                    if node_subfield.text and node_subfield.text != '':
                        subfield = SubField()
                        subfield.value = unescape(node_subfield.text)
                        if flag_html_unescape:
                            subfield.value = html_unescape(subfield.value)
                        subfield.value = subfield.value.strip()
                        subfield.code = node_subfield.attrib['code']
                        dfield.subfields.append(subfield)
            
            mr_list.append(mr)        

        return mr_list

    def addDataField(self,df):
        self.datafields.append(df)

    # propably doesnt work for edge cases
    def addDataFieldAfter(self,df,tag):
        i = 0
        while i < len(self.datafields) and self.datafields[i].tag <= tag:
            i += 1
        self.datafields.insert(i,df)
    
    def addControlField(self,cf):
        self.controlfields.append(cf)

    def getControlFieldsForTag(self,tag) -> List[ControlField]:
        matchingfields=[]
    
        for cf in self.controlfields:
            if cf.tag == tag:
                matchingfields.append(cf)

        return matchingfields

    def getDataFieldsForTag(self,tag,ind1='-',ind2='-') -> List[DataField]:
        matchingfields = []
        
        for df in self.datafields:
            if df.tag != tag:
                continue

            if ind1 != '-' and ind1 != df.ind1:
                continue
            
            if ind2 != '-' and ind2 != df.ind2:
                continue
            
            matchingfields.append(df)
        
        return matchingfields

    def getDataFieldsForTags(self,*tags) -> List[DataField]:
        dfs = [f for f in self.datafields if f.tag in tags]
        return dfs

    def removeDataFieldsForTag(self,tag,ind1 = '-',ind2 = '-'):
        self.datafields[:] = [df for df in self.datafields if not ((tag == df.tag) and (tag == '-' or ind1 != df.ind1) and (ind2 == '-' or ind2 != df.ind2))]

    def removeDataFieldsExcept(self,*tags):
        self.datafields[:] = [f for f in self.datafields if f.tag in tags]
    
    def removeControlFieldsExcept(self,*tags):
        self.controlfields[:] = [f for f in self.controlfields if f.tag in tags]

    def getCreationDate(self):
        date = None
        fields = self.getControlFieldsForTag('008')
        if fields:
            f = fields[0]
            date = f.value[0:6]
        return date

    def getModificationDate(self):
        date = None
        fields = self.getControlFieldsForTag('005')
        if fields:
            f = fields[0]
            date = f.value[0:8]
        return date

    def isDeleted(self):
        deleted = True if self.leader[5]=='d' else False
        return deleted

    def isBook(self):
        if self.leader[6] == '#' or self.leader[6] == 't': return True
        if self.leader[6] == 'a' and self.leader[7] in ('a','c','d','m'): return True
        return False

    def getMMSId(self):
        return self.getControlFieldsForTag('001')[0].value

    def getAC(self):
        if self.getControlFieldsForTag('009'):
            return self.getControlFieldsForTag('009')[0].value
        else:
            return None

    def getTitle(self,extended=False):
        str = None
        ext = None

        datafields = self.getDataFieldsForTag('245','0','0');
        if datafields:
            datafield = datafields[0]
            subfields = datafield.subfields
            for subfield in subfields:
                if subfield.code == 'a':
                    str = subfield.value
        else:
            datafields = self.getDataFieldsForTag('245','-','-');
            if datafields:
                datafield = datafields[0]
                subfields = datafield.subfields
                for subfield in subfields:
                    if subfield.code == 'a':
                        str = subfield.value

        if extended:
            datafields = self.getDataFieldsForTag('246','3',' ');
            if datafields:
                datafield = datafields[0]
                subfields = datafield.subfields
                for subfield in subfields:
                    if subfield.code == 'a':
                        ext = subfield.value

        if ext:
            str += "; " + ext

        return str

    def getAuthor(self):
        str = None

        datafields = self.getDataFieldsForTag('100','1','-')
        if datafields:
            datafield = datafields[0]

            if datafield is not None:
                subfields = datafield.subfields
                for subfield in subfields:
                    if subfield.code == 'a':
                        str = subfield.value
        else:
            datafields = self.getDataFieldsForTag('700','1','-')
            if datafields:
                datafield = datafields[0]
                if datafield is not None:
                    subfields = datafield.subfields
                    for subfield in subfields:
                        if subfield.code == 'a':
                            str = subfield.value
        
        return str

    def getPublisher(self):
        str = None

        datafields = self.getDataFieldsForTag('264','-','-')
        if datafields:
            datafield = datafields[0]

            if datafield is not None:
                subfields = datafield.subfields
                for subfield in subfields:
                    if subfield.code == 'b':
                        str = subfield.value
        
        return str

    def getISSN(self):
        str = None

        datafields = self.getDataFieldsForTag('022','-','-')
        if datafields:
            datafield = datafields[0]

            if datafield is not None:
                subfields = datafield.subfields
                for subfield in subfields:
                    if subfield.code == 'a':
                        str = subfield.value
        
        return str

    def getISSNs(self) -> List[str]:
        l:List[str] = []
        df: DataField
        sf: SubField

        for df in self.getDataFieldsForTag('022','-','-'):
            for sf in df.subfields:
                if sf.code == 'a':
                    if sf.value not in l: l.append(sf.value)
        return l

    def getLinkISSNs(self) -> List[str]:
        l:List[str] = []
        df: DataField
        sf: SubField

        for df in self.getDataFieldsForTag('022','-','-'):
            for sf in df.subfields:
                if sf.code == 'l':
                    if sf.value not in l: l.append(sf.value)
        return l

    def getISSN_776(self):
        str = None

        datafields = self.getDataFieldsForTag('776','-','-')
        if datafields:
            datafield = datafields[0]

            if datafield is not None:
                subfields = datafield.subfields
                for subfield in subfields:
                    if subfield.code == 'x':
                        str = subfield.value
        
        return str


    def getYear(self,ind1=' ',ind2='1'):
        str = None

        datafields = self.getDataFieldsForTag('264',ind1,ind2)
        if datafields:
            datafield = datafields[0]

            if datafield is not None:
                subfields = datafield.subfields
                for subfield in subfields:
                    if subfield.code == 'c':
                        str = subfield.value
        
        if str is None and (ind1 != '-' or ind2 != '-'):
            return self.getYear(ind1 = '-',ind2 = '-')

        return str

    def isHSS(self) -> bool:
        df:DataField
        sf:SubField

        dfs = self.getDataFieldsForTag('970','2')
        for df in dfs:
            sfs = df.getSubFieldsWithCode('d')
            for sf in sfs:
                if sf.value[0:2] == 'HS':
                    return True

        return False


    # checks for miscellaneous keyword types
    def hasBK(self) -> bool:
        df:DataField
        sf:SubField

        dfs = self.getDataFieldsForTag('084')
        for df in dfs:
            sfs = df.getSubFieldsWithCode('2')
            for sf in sfs:
                if sf.value in ['bk','bkl']:
                    return True

        return False

    def hasSinglePersonKeyword(self) -> bool:
        dfs = self.getDataFieldsForTag('600')
        return True if dfs else False

    def hasSingleTimeKeyword(self) -> bool:
        dfs = self.getDataFieldsForTag('648')
        return True if dfs else False

    def hasSingleSubjectKeyword(self) -> bool:
        dfs = self.getDataFieldsForTag('650')
        return True if dfs else False

    def hasSingleGeographictKeyword(self) -> bool:
        dfs = self.getDataFieldsForTag('651')
        return True if dfs else False

    def hasSingleKeyword(self) -> Tuple[int,int]:
        cnt_kw:int = 0
        cnt_kw_gnd:int = 0
        dfs:List[DataField] = []
        dfs.extend(self.getDataFieldsForTag('600'))
        dfs.extend(self.getDataFieldsForTag('648'))
        dfs.extend(self.getDataFieldsForTag('650'))
        dfs.extend(self.getDataFieldsForTag('651'))
        for df in dfs:
            cnt_kw += 1
            sfs = df.getSubFieldsWithCode('0')
            for sf in sfs:
                if sf.value[0:8] == '(DE-588)':
                    cnt_kw_gnd += 1

        return cnt_kw,cnt_kw_gnd

    def hasFreeKeyword(self) -> int:
        dfs = self.getDataFieldsForTag('653')
        return len(dfs)

    def hasFormKeyword(self) -> Tuple[int,int]:
        cnt_kw:int = 0
        cnt_kw_gnd:int = 0
        dfs:List[DataField] = self.getDataFieldsForTag('655')
        for df in dfs:
            cnt_kw += 1
            sfs = df.getSubFieldsWithCode('0')
            for sf in sfs:
                if sf.value[0:8] == '(DE-588)':
                    cnt_kw_gnd += 1

        return cnt_kw,cnt_kw_gnd

    def hasTUSys(self) -> Tuple[bool,bool]:
        tu_sys: bool = False
        tu_sys_2022: bool = False
        tu_sys_2023: bool = False
        tu_sys_2024: bool = False
        tu_sys_2025: bool = False        
        dfs = self.getDataFieldsForTag('983')
        if dfs:
            tu_sys = True
        for df in dfs:
             sfs = df.getSubFieldsWithCode('z')
             for sf in sfs:
                 if sf.value[0:4] == '2022':
                    tu_sys_2022 = True
                 if sf.value[0:4] == '2023':
                    tu_sys_2023 = True
                 if sf.value[0:4] == '2024':
                    tu_sys_2024 = True
                 if sf.value[0:4] == '2025':
                    tu_sys_2025 = True

        return tu_sys,tu_sys_2022,tu_sys_2023,tu_sys_2024,tu_sys_2025

    def hasRSWKKeyword(self) -> Tuple[int,int]:
        cnt_kw:int = 0
        cnt_kw_gnd:int = 0
        dfs:List[DataField] = self.getDataFieldsForTag('689')

        for df in dfs:
            cnt_kw += 1
            sfs = df.getSubFieldsWithCode('0')
            for sf in sfs:
                if sf.value[0:8] == '(DE-588)':
                    cnt_kw_gnd += 1

        return cnt_kw,cnt_kw_gnd        

    def hasHSSAuthorKeywordDe(self) -> bool:
        dfs = self.getDataFieldsForTag('971',ind1='8')
        return True if dfs else False

    def hasHSSAuthorKeywordEn(self) -> bool:
        dfs = self.getDataFieldsForTag('971',ind1='9')
        return True if dfs else False


    def holGetLibraryLocation(self) -> Tuple[str,str,str]:
        library = location = callnumber = None
        df = self.getDataFieldsForTag('852')[0]
        sfs = df.getSubFieldsWithCode('b')
        if sfs:
            library = df.getSubFieldsWithCode('b')[0].value
        sfs = df.getSubFieldsWithCode('c')
        if sfs:
            location = df.getSubFieldsWithCode('c')[0].value
        sfs = df.getSubFieldsWithCode('h')
        if sfs:
            callnumber = df.getSubFieldsWithCode('h')[0].value
        return library,location,callnumber

    def holGetCoverages(self,holid:str,ignore_holding_issues) -> Tuple[List[Coverage],List[str]]:
        DIR_DOWN = 0
        DIR_UP = 1

        def decodeReportingYear(s:str):
            if match := PATTERN_DECODE_REPORTING_YEAR.match(s):
                groups = match.groups()
                s = groups[0] 
                s = s[1:-1]
            return s               

        def decodeMultiYear(s:str,direction:int):
            if not s:
                return s
#            print ("s",s)
            if '/' in s:
                l = s.split('/')
                if direction == DIR_DOWN:
                    return l[0]
                else:
                    (a,b) = (l[0],l[1])
#                    print (a,b)
                    if len(b) == 4:
                        return b
                    else:
                        i = int(a[0:2])
                        j = int(a[2:])
                        k = int(b)
                        if j <= k:
                            s = str(i) + str(k).rjust(2,'0')
                        else:
                            s = str(i+1) + str(k).rjust(2,'0')
            return s

        def decodeMultiVolume(s:str,direction:int):
            if not s:
                return s
            if '/' in s:
                l = s.split('/')
                if direction == DIR_DOWN:
                    s = l[0]
                else:
                    s = l[1]
            return s


        def decodeMultiIssue(s:str) -> List[Tuple[str,str]]:
            l_out: List[Tuple[str,str]] = []

            if not s:
                return l_out
            l = s.split(',')
            for x in l:
                m = x.split('-')
                a = m[0]
                b = m[1] if len(m) == 2 else a
                l_out.append((a,b))

            return l_out


        l: List[Coverage] = []
        errs: List[str] = []
        df: DataField
        sf: SubField
        l_86630: List[str] = []
        l_cov: List[str] = []

        for df in self.getDataFieldsForTag('866','3','0'):
            for sf in df.subfields:
                if sf.code == 'a':
                    l_86630.append(sf.value)

        for x in l_86630:
            l_cov.extend(x.split(';'))
        l_cov = [x.strip() for x in l_cov]

        try:
            for i,x in enumerate(l_cov):
                id = str(holid) + ';' +str(i)

                if x == "nur laufender Jahrgang":
                    x = datetime.datetime.now().strftime('%Y')
                    x = x + ' - ' + x
                if x.endswith(' -'): x += ' '
                still_running = True if ' - ' in x else False

                m = x.split(' - ')
                if len(m) == 1:
                    if not still_running:
                        (start,end) = (m[0],m[0])
                    else:
                        (start,end) = (m[0],None)
                elif len(m) == 2:
                    (start,end) = (m[0],m[1])
                else:
                    errs.append("invalid coverage, too many parts {}".format(x))
                    continue

                start = start.strip() if start else ''
                end = end.strip() if end else ''

                if ignore_holding_issues:
                    if match := PATTERN_IGNORE_HOLDING_ISSUES.match(start):
                        groups = match.groups()
                        start = groups[0]

                    if match := PATTERN_IGNORE_HOLDING_ISSUES.match(end):
                        groups = match.groups()
                        end = groups[0]

                year_start = volume_start = issue_start = None
                year_end = volume_end = issue_end = None
                matched_start = matched_end = False
                for key,pattern in MAP_PATTERN.items():
                    if match := pattern.search(start):
                        groups = match.groups()
                        if key == KEY_VOLUME_YEAR_ISSUE:
                            volume_start=groups[0]
                            year_start=groups[1]
                            issue_start=groups[2]
                        if key == KEY_VOLUME_YEAR:
                            volume_start=groups[0]
                            year_start=groups[1]
                        if key == KEY_YEAR:
                            year_start=groups[0]

                        year_start = decodeReportingYear(year_start)
                        year_start = decodeMultiYear(year_start,DIR_DOWN)
                        volume_start = decodeMultiVolume(volume_start,DIR_DOWN)
                        l_issuelist = decodeMultiIssue(issue_start)

                        matched_start = True
                        break

                if end:
                    for key,pattern in MAP_PATTERN.items():
                        if match := pattern.match(end):
                            groups = match.groups()
                            if key == KEY_VOLUME_YEAR_ISSUE:
                                volume_end=groups[0]
                                year_end=groups[1]
                                issue_end=groups[2]
                            if key == KEY_VOLUME_YEAR:
                                volume_end=groups[0]
                                year_end=groups[1]
                            if key == KEY_YEAR:
                                year_end=groups[0]

                            year_end = decodeReportingYear(year_end)
                            year_end = decodeMultiYear(year_end,DIR_UP)
                            volume_end = decodeMultiVolume(volume_end,DIR_UP)

                            matched_end = True
                            break
                else:
                    if not still_running:
                        (year_end,volume_end,issue_end) = (year_start,volume_start,issue_start)
                    matched_end = True

                if matched_start and matched_end:
                    if l_issuelist:
                        for y in l_issuelist:
                            (issue_start,issue_end,year_end_x,volume_end_x) = (y[0],y[1],year_start,volume_start)
                            coverage = Coverage(id, 
                                            volume_start=volume_start,
                                            year_start=year_start,
                                            issue_start=issue_start,
                                            volume_end=volume_end_x,
                                            year_end=year_end_x,
                                            issue_end=issue_end)
                            l.append(coverage)
                            if coverage.errs:
                                errs.append("coverage can't be normalized {}".format(x))
                                errs.extend(coverage.errs)
                    
                    else:
                        coverage = Coverage(id, 
                                            volume_start=volume_start,
                                            year_start=year_start,
                                            issue_start=issue_start,
                                            volume_end=volume_end,
                                            year_end=year_end,
                                            issue_end=issue_end)
                        l.append(coverage)
                        if coverage.errs:
                            errs.append("coverage can't be normalized {}".format(x))
                            errs.extend(coverage.errs)
                else:
                    errs.append("invalid coverage {}".format(x))
        except Exception as e:
            print (traceback.format_exc())
            print (e)
            print ("holding: ",x,holid)
            raise e    
            #errs.append("invalid coverage {}".format(x))
        
        return l,errs

    def getVirtualHoldings(self):
        hols = {}
        dfs = self.getDataFieldsForTag('852')
        for df in dfs:
            sfs = df.getSubFieldsWithCode('8')
            if sfs:
                holid = sfs[0].value
                mr = MarcRecord()
                mr.addDataField(df)
                hols[holid] = mr
        dfs = self.getDataFieldsForTag('866')
        for df in dfs:
            sfs = df.getSubFieldsWithCode('8')
            if sfs:
                holid = sfs[0].value
                match = re.search('(\d+)\.\d+',holid)
                holid = match[1]
                mr = hols[holid]
                mr.addDataField(df)

        return hols

    @classmethod
    def holSortByCoverage(cls,holdings):
        holdings:List[MarcRecord] = [x for x in holdings]
        errs:List[str] = []

        coverages:List[Coverage]
        hol:MarcRecord

        try:
            for hol in holdings:
                coverages,e = hol.holGetCoverages(hol.holid,ignore_holding_issues=True)
                if coverages and not e:
                    coverages.sort()
                    hol.lowest_coverage = coverages[0]
                else:
                    hol.lowest_coverage = None
                    errs.extend(e)

            holdings.sort(key=lambda x: x.lowest_coverage.getCoverageStringStart())
        except:
            errs.append('error sorting holdings by coverage')

        return holdings,errs
    
    @classmethod
    def getSortableCallNumber(cls,cn):
        if not cn: return cn
        if match := re.match('(\d+)(.*)',cn):
            num_part = match[1]
            rest = match[2]
            cn = num_part.zfill(6) + rest

        return cn

    def debug(self):
        print("leader = "+self.leader)

    def countFields(self):
        field_count = {}

        if self.leader:
            field_count['LDR'] = 1
        for f in self.controlfields:
            if f.tag in field_count:
                cnt = field_count[f.tag]
                cnt += 1
                field_count[f.tag] = cnt
            else:
                field_count[f.tag] = 1
        for f in self.datafields:
            if f.tag in field_count:
                cnt = field_count[f.tag]
                cnt += 1
                field_count[f.tag] = cnt
            else:
                field_count[f.tag] = 1

        return field_count

    def toXML(self):
        xml = self.toRecordXML()
        xml = '<bib>'+xml+'</bib>'

        return xml

    def toBibXML(self):
        return self.toXML()

    def toHoldingXML(self):
        xml = self.toRecordXML()
        xml = '<holding>'+xml+'</holding>'

        return xml

    def toRecordXML(self):
        xml = ''
        xml+='<record>'
        if self.leader:
            xml+='<leader>'+self.leader+'</leader>'  
        for controlfield in self.controlfields:
            xml+='<controlfield '
            xml+='tag="'+controlfield.tag+'">'
            xml+=controlfield.value
            xml+='</controlfield>'
          
        try:
            for datafield in self.datafields:
                xml+='<datafield '
                xml+='tag="'+datafield.tag+'" '
                xml+='ind1="'+datafield.ind1+'" '
                xml+='ind2="'+datafield.ind2+'">'
                for subfield in datafield.subfields:
                    xml+='<subfield code="'
                    xml+=subfield.code+'">'
                    xml+=escape(subfield.value.strip())
                    xml+='</subfield>'
                xml+='</datafield>'
        except Exception as e:
            print (datafield.tag)
            print (datafield.ind1)
            print (datafield.ind2)
            raise Exception(str(e))
        xml+='</record>'

        return xml

    def toDublinCore(self,map_key=None) -> Tuple[DublinCore,str]:

        def value_in_patterns(value,patterns):
            matched = False
            i = 0
            while not matched and i<len(patterns):
                pattern = patterns[i]
                if match := re.search(pattern,value):
                    matched = True
                i += 1

            return matched

        def ids_hss():
            values = []
            dfs = self.getDataFieldsForTag('856')
            for df in dfs:
                sfs = df.getSubFieldsWithCodes('u')
                vals = [sf.value for sf in sfs if sf.value.find('media.obvsg.at')==-1]
                values.extend(vals)

            dfs = self.getDataFieldsForTag('024')
            for df in dfs:
                id_type = df.getSubFieldsWithCodes('2')[0].value
                id_value = df.getSubFieldsWithCodes('a')[0].value
                if id_type =='doi':
                    val = 'doi' + ':' + id_value
                    values.append(val)
                elif id_type =='urn':
                    val = id_value
                    values.append(val)

            return values

        def derive_mapping():
            map_key = None

            mmsid = self.getMMSId()
            # Journal for Facility Management, Der öffentliche Sektor
            if map_key is None:
                dfs = self.getDataFieldsForTag('773')
                for df in dfs:
                    sfs = df.getSubFieldsWithCodes('w')
                    for sf in sfs:
                        if sf.value in ['(AT-OBV)AC13348910', '(AT-OBV)AC10863779']:
                            map_key = MARC21_DC_MAP_OES_JFM

            # HSS
            if map_key is None:
                check_970_a = False
                check_970_d = False
                dfs = self.getDataFieldsForTag('970')
                for df in dfs:
                    sfs = df.getSubFieldsWithCodes('a')
                    for sf in sfs:
                        if sf.value == 'TUW':
                            check_970_a = True

                    sfs = df.getSubFieldsWithCodes('d')
                    for sf in sfs:
                        if sf.value in ['HS-DIPL', 'HS-DISS', 'HS-MASTER', 'HS-HABIL']:
                            check_970_d = True

                if check_970_a and check_970_d:
                    map_key = MARC21_DC_MAP_HSS
                
            if map_key is None:
                map_key = MARC21_DC_MAP_GENERIC

            logging.debug(f"mapping for {mmsid}: {map_key}")
            return map_key


        # depends on Python >=3.7 having dicts being ordered by insertion order
        # use subfields: None for no subfield filtering
        maps = {
            MARC21_DC_MAP_GENERIC:  {
                'fields': DC_FIELDS,
                'rules': 
                    {
                        DC_FIELD_TITLE: 
                        [
                            {
                                'tags': ['245'],
                                'subfields': ['a','b'],
                                'subfield_sep': ' : ',
                            }
                        ],
                        DC_FIELD_CREATOR: 
                        [
                            {
                                'tags': ['100','110','111','700','710','711','720'],
                                'subfields': ['a'],
                            }
                        ],
                        DC_FIELD_SUBJECT:
                        [
                            {
                                'tags': ['600','610','611','630','653'],
                                'subfields': 'a',
                            },
                            {
                                'tags': ['650'],
                                'subfields': None,
                                'ignore_subfields': ['0','2'],
                            },
                            {
                                'tags': ['983'],
                                'subfields': ['d'],
                            }
                        ],
                        DC_FIELD_LANGUAGE:
                        [
                            {
                                'controltags': ['008'],
                                'positions': (35,38),
                            },
                            {
                                'tags': ['546'],
                                'subfields': None,
                            }
                        ],
                        DC_FIELD_COVERAGE:
                        [
                            {
                                'tags': ['651','752'],
                                'subfields': ['a'],
                            }
                        ],
                        DC_FIELD_RIGHTS:
                        [
                            {
                                'tags': ['506'],
                                'subfields': ['a','f'],
                            },
                            {
                                'tags': ['542'],
                                'subfields': ['u'],
                            },
                        ],
                        DC_FIELD_FORMAT:
                        [
                            {
                                'tags': ['856'],
                                'subfields': ['q'],
                            }
                        ],
                        DC_FIELD_IDENTIFIER:
                        [
                            {
                                'tags': ['856'],
                                'subfields': ['u'],
                                'allowed_patterns': ['doi.org'],
                            }
                        ],
                        DC_FIELD_SOURCE:
                        [
                            {
                                'tags': ['786'],
                                'subfields': ['o','t'],
                            }
                        ],
                        DC_FIELD_PUBLISHER:
                        [
                            {
                                'tags': ['264'],
                                'subfields': ['b'],
                            }
                        ],
                        DC_FIELD_DESCRIPTION:
                        [
                            {
                                'tags': [str(x) for x in range(500,600) if x not in (506,530,540,546)],
                                'not_allowed_patterns': ['Enthält Literaturangaben'],
                            }
                        ],
                        DC_FIELD_DATE:
                        [
                            {
                                'tags': ['264'],
                                'subfields': ['c'],
                            }
                        ]
                    }
            },  
            MARC21_DC_MAP_HSS:  {
                'fields': DC_FIELDS,
                'rules': 
                    {
                        DC_FIELD_TITLE: 
                        [
                            {
                                'tags': ['245'],
                                'subfields': ['a','b'],
                                'subfield_sep': ' : ',
                            }
                        ],
                        DC_FIELD_CREATOR: 
                        [
                            {
                                'tags': ['100','110','111','700','710','711','720'],
                                'subfields': ['a'],
                            }
                        ],
                        DC_FIELD_SUBJECT:
                        [
                            {
                                'tags': ['600','610','611','630','653'],
                                'subfields': None,
                            },
                            {
                                'tags': ['650'],
                                'subfields': None,
                                'ignore_subfields': ['0'],
                            },
                            {
                                'tags': ['983'],
                                'subfields': ['d'],
                            },
                            {
                                'tags': ['9718 ','9719 '],
                                'subfields': ['a'],
                                'split_contents_char': '/'
                            }
                        ],
                        DC_FIELD_LANGUAGE:
                        [
                            {
                                'controltags': ['008'],
                                'positions': (35,38),
                            },
                            {
                                'tags': ['546'],
                                'subfields': None,
                            }
                        ],
                        DC_FIELD_COVERAGE:
                        [
                            {
                                'tags': ['651','752'],
                                'subfields': None,
                            }
                        ],
                        DC_FIELD_RIGHTS:
                        [
                            {
                                'tags': ['506'],
                                'subfields': ['a','f'],
                            },
                            {
                                'tags': ['542'],
                                'subfields': ['u'],
                            },
                        ],
                        DC_FIELD_FORMAT:
                        [
                            {
                                'fixed': 'application/pdf',
                            }
                        ],
                        DC_FIELD_IDENTIFIER:
                        [
                            {
                                'special': 'ids_hss'
                            }
                        ],
                        DC_FIELD_SOURCE:
                        [
                            {
                                'tags': ['786'],
                                'subfields': ['o','t'],
                            }
                        ],
                        DC_FIELD_PUBLISHER:
                        [
                            {
                                'tags': ['264'],
                                'subfields': ['b'],
                            }
                        ],
                        DC_FIELD_DESCRIPTION:
                        [
                            {
                                'tags': ['520'],
                                'subfields': ['a'],
                                'value_from_position': 5,
                                'not_allowed_patterns': ['Enthält Literaturangaben'],
                            }
                        ],
                        DC_FIELD_DATE:
                        [
                            {
                                'tags': ['264'],
                                'subfields': ['c'],
                            }
                        ],
                        DC_FIELD_TYPE:
                        [
                            {
                                'tags': ['9702 '],
                                'subfields': ['d'],
                            }
                        ],
                    }
            },
            MARC21_DC_MAP_OES_JFM:  {
                'fields': DC_FIELDS,
                'rules': 
                    {
                        DC_FIELD_TITLE: 
                        [
                            {
                                'tags': ['245'],
                                'subfields': ['a','b'],
                                'subfield_sep': ' : ',
                            }
                        ],
                       DC_FIELD_CREATOR: 
                        [
                            {
                                'tags': ['100','110','111','700','710','711','720'],
                                'subfields': ['a'],
                            }
                        ],
                        DC_FIELD_SUBJECT:
                        [
                            {
                                'tags': ['600','610','611','630','653'],
                                'subfields': None,
                            },
                            {
                                'tags': ['650'],
                                'subfields': None,
                                'ignore_subfields': ['0'],
                            },
                            {
                                'tags': ['983'],
                                'subfields': ['d'],
                            }
                        ],
                        DC_FIELD_LANGUAGE:
                        [
                            {
                                'controltags': ['008'],
                                'positions': (35,38),
                            },
                            {
                                'tags': ['546'],
                                'subfields': None,
                            }
                        ],
                        DC_FIELD_COVERAGE:
                        [
                            {
                                'tags': ['651','752'],
                                'subfields': None,
                            }
                        ],
                        DC_FIELD_RIGHTS:
                        [
                            {
                                'tags': ['506'],
                                'subfields': ['a'],
                                'allowed patterns': ['Open Access'],
                                'transform': 'lower'
                            },
                            {
                                'tags': ['542'],
                                'subfields': ['u'],
                            },
                        ],
                        DC_FIELD_IDENTIFIER:
                        [
                            {
                                'tags': ['856'],
                                'subfields': ['u'],
                                'allowed_patterns': ['doi.org'],
                            }
                        ],
                        DC_FIELD_SOURCE:
                        [
                            {
                                'tags': ['786'],
                                'subfields': ['o','t'],
                            }
                        ],
                        DC_FIELD_PUBLISHER:
                        [
                            {
                                'tags': ['264'],
                                'subfields': ['b'],
                            }
                        ],
                        DC_FIELD_DESCRIPTION:
                        [
                            {
                                'tags': ['520'],
                                'subfields': ['a'],
                                'value_from_position': 5,
                                'not_allowed_patterns': ['Enthält Literaturangaben'],
                            }
                        ],
                        DC_FIELD_TYPE:
                        [
                            {
                                'fixed': 'journal article'
                            }
                        ],
                        DC_FIELD_FORMAT:
                        [
                            {
                                'fixed': 'application/pdf',
                            }
                        ],
                        DC_FIELD_DATE:
                        [
                            {
                                'tags': ['264'],
                                'subfields': ['c'],
                            }
                        ]
                    }
            }   
        }

        if map_key is None:
            map_key = derive_mapping()
        m = maps[map_key]
        dc = DublinCore()
        l = m['fields']
        r = m['rules']
        for f in l:
            if f in r:
                rule_list_for_dc_tag = r[f]
                for rule in rule_list_for_dc_tag:
#                    logging.debug(rule)
                    marc_tags = rule['tags'] if 'tags' in rule else []
                    subfields = rule['subfields'] if 'subfields' in rule else []
                    ignore_subfields = rule['ignore_subfields'] if 'ignore_subfields' in rule else []
                    subfield_sep = rule['subfield_sep'] if 'subfield_sep' in rule else '; '
                    control_tags = rule['controltags'] if 'controltags' in rule else []
                    positions = rule['positions'] if 'positions' in rule else []
                    allowed_patterns = rule['allowed_patterns'] if 'allowed_patterns' in rule else []
                    not_allowed_patterns = rule['not_allowed_patterns'] if 'not_allowed_patterns' in rule else []
                    value_from_position = rule['value_from_position'] if 'value_from_position' in rule else None
                    special = rule['special'] if 'special' in rule else None
                    fixed = rule['fixed'] if 'fixed' in rule else None
                    transform = rule['transform'] if 'transform' in rule else None
                    split_contents_char = rule['split_contents_char'] if 'split_contents_char' in rule else None
                    
                    # fixed content
                    if fixed:
                        dc.addField(DCField(f,fixed))

                    # function calls for special handling
                    elif special:
                        call = locals()[special]
                        dcvalues = call()
                        for dcvalue in dcvalues:
                            dc.addField(DCField(f,dcvalue))

                    else:
                        for tag in marc_tags:
                            ind1 = '-'
                            ind2 = '-'
                            if len(tag)>3:
                                ind1 = tag[3]
                                ind2 = tag[4]
                                tag = tag[0:3]
                            dfs = self.getDataFieldsForTag(tag,ind1,ind2)
                            for df in dfs:
                                if subfields:
                                    sfs = df.getSubFieldsWithCodes(*subfields)
                                else:
                                    sfs = df.subfields
                                if ignore_subfields:
                                    sfs[:] = [sf for sf in sfs if sf.code not in ignore_subfields]                              
                                values = [sf.value for sf in sfs]
                                if allowed_patterns:
                                    values[:] = [value for value in values if value_in_patterns(value,allowed_patterns)]
                                if not_allowed_patterns:
                                    values[:] = [value for value in values if not value_in_patterns(value,not_allowed_patterns)]
                                if value_from_position:
                                    values[:] = [value[5:] for value in values]

                                if split_contents_char:
                                    vals = []
                                    for v in values:
                                        v_inner = v.split(split_contents_char)
                                        v_inner[:] = [v.strip() for v in v_inner]
                                        vals.extend(v_inner)
                                    values = vals
                                    for v in values:
                                        dc.addField(DCField(f,v))

                                else:
                                    dcvalue = subfield_sep.join(values)
                                    if dcvalue:
                                        if transform and transform == 'lower':
                                            dcvalue = dcvalue.lower()
                                        dc.addField(DCField(f,dcvalue))

                        for tag in control_tags:
                            cfs = self.getControlFieldsForTag(tag)
                            for cf in cfs:
                                dcvalue = cf.value[positions[0]:positions[1]]
                                dc.addField(DCField(f,dcvalue))

        return dc,map_key

class ControlField:
    tag: str 
    value: str

    def __init__(self):
        self.tag = None
        self.value = None

    @classmethod
    def createControlField(cls,tag,value) -> ControlField:
        cf = ControlField()
        cf.tag = tag
        cf.value = value
        return cf

class DataField:
    tag: str
    ind1: str
    ind2: str
    subfields: List[SubField]

    def __init__(self):
        self.tag = None
        self.ind1 = None
        self.ind2 = None
        self.subfields=[]
    
    def __str__(self):
        s = ''
        s += self.tag
        s += self.ind1
        s += self.ind2
        for sf in self.subfields:
            s += ' '
            s += '|' + sf.code
            s += ' '
            s += sf.value

    @classmethod
    def createDataField(cls,tag,ind1,ind2) -> DataField:
        df = DataField()
        df.tag = tag
        df.ind1 = ind1
        df.ind2 = ind2
        return df

    def addSubField(self,subfield):
        self.subfields.append(subfield)
    
    def getSubFieldsWithCode(self,code) -> List[SubField]:
        sfs = [sf for sf in self.subfields if sf.code == code]
        return sfs

    def getSubFieldsWithCodes(self,*codes) -> List[SubField]:
        sfs = [sf for sf in self.subfields if sf.code in codes]
        return sfs

    def getSubFieldsWithCodesExcept(self,*codes) -> List[SubField]:
        """Returns a list of all the datafield's subfields except those having their code in *codes"""
        sfs = [sf for sf in self.subfields if sf.code not in codes]
        return sfs

    def removeSubFieldsWithCode(self,code):
        self.subfields[:] = [sf for sf in self.subfields if sf.code != code]

    def removeSubFieldsWithCodesExcept(self,*codes):
        """Removes all the datafield's subfields except those having their code _not_ in *codes, put another way: retains all subfields having their code in *codes"""
        self.subfields[:] = [sf for sf in self.subfields if sf.code in codes]

    def removeSubFieldsWithCodeExceptSF4othExists(self,code):
        sfs = self.getSubFieldsWithCode('4')
        found = False
        for sf in sfs:
            if sf.value == 'oth':
                found = True

        if not found:
            self.subfields[:] = [sf for sf in self.subfields if sf.code != code]

    def setOrAddSubField(self,code,value):
        sfs = [sf for sf in self.subfields if sf.code == code]
        if sfs:
            for sf in sfs:
                sf.value = value
        else:
            self.addSubField(SubField.createSubField(code,value))
    
    def changeSubFieldCode(self,old,new):
        for sf in self.subfields:
            if sf.code == old:
                sf.code = new
class SubField:
    code: str
    value: str

    def __init__(self):
        self.code = None
        self.value = None

    @classmethod
    def createSubField(cls,code,value) -> SubField:
        sf = SubField()
        sf.code = code
        sf.value = value
        return sf

class DublinCore:
    fields: List[DCField]

    def __init__(self):
        self.fields = []
    
    def addField(self,field: DCField):
        self.fields.append(field)

    def fieldExists(self,tag):
        found = False
        i = 0
        while not found and i<len(self.fields):
            if self.fields[i].tag == tag:
                found = True
            i += 1

        return found

    def toXML(self,add_namespace=True):
        xml = ''
        
        xml += '<'
        if add_namespace:
            xml += 'oai_dc:'
        xml += 'dc'
        if add_namespace:
            xml += ' xmlns:oai_dc="http://www.openarchives.org/OAI/2.0/oai_dc/" '
            xml += 'xmlns:dc="http://purl.org/dc/elements/1.1/" '
            xml += 'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            xml += 'xsi:schemaLocation="http://www.openarchives.org/OAI/2.0/oai_dc/ '
            xml += 'http://www.openarchives.org/OAI/2.0/oai_dc.xsd"'
        xml += '>'
        for f in self.fields:
            if add_namespace:
                xml += f'<dc:{f.tag}>{escape(f.value)}</dc:{f.tag}>'
            else:
                xml += f'<{f.tag}>{escape(f.value)}</{f.tag}>'
        xml += '</'
        if add_namespace:
            xml += 'oai_dc:'
        xml += 'dc>'

        return xml

    # DC_SOURCE recommended as well, but references / citations not available for HSS
    def checkBaseCompleteness(self):
        required_fields = [ DC_FIELD_TITLE, DC_FIELD_IDENTIFIER, DC_FIELD_CREATOR,
            DC_FIELD_DATE, DC_FIELD_TYPE, DC_FIELD_LANGUAGE ]
        missing_fields = []
        complete = True
        for f in required_fields:
            if not self.fieldExists(f):
                missing_fields.append(f)

        complete = True if len(missing_fields)==0 else False
        return complete, missing_fields

    # DC_SOURCE recommended as well, but references / citations not available for HSS
    def checkOKMCompleteness(self):
        required_fields = [ DC_FIELD_TITLE, DC_FIELD_IDENTIFIER, DC_FIELD_CREATOR,
            DC_FIELD_DATE, DC_FIELD_TYPE, DC_FIELD_LANGUAGE, DC_FIELD_DESCRIPTION, DC_FIELD_SUBJECT ]
        missing_fields = []
        complete = True
        for f in required_fields:
            if not self.fieldExists(f):
                missing_fields.append(f)

        complete = True if len(missing_fields)==0 else False
        return complete, missing_fields

    def postProcess(self,map_key):
        record_ok = True
        errors = []

        if map_key == MARC21_DC_MAP_HSS:
            # check type
            if record_ok:
                fields = [f for f in self.fields if f.tag == DC_FIELD_TYPE]
                if len(fields)>1:
                    record_ok=False
                    errors.append(f'multiple occurences for {DC_FIELD_TYPE}')
                else:
                    for f in fields:
                        if f.value in ['HS-DIPL','HS-MASTER']:
                            f.value = 'info:eu-repo/semantics/masterThesis'
                        elif f.value in ['HS-DISS','HS-HABIL']:
                            f.value = 'info:eu-repo/semantics/doctoralThesis'
                        else:
                            record_ok = False
                            errors.append(f'unexpected value for {DC_FIELD_TYPE}: {f.value}')

            # check type
            if record_ok:
                filter_fields = [f for f in self.fields if f.tag == DC_FIELD_LANGUAGE and f.value not in ['eng','ger']]
                self.fields[:] = [f for f in self.fields if f not in filter_fields]
                fields = [f for f in self.fields if f.tag == DC_FIELD_LANGUAGE]
                if len(fields)>1:
                    record_ok=False
                    errors.append(f'multiple occurences for {DC_FIELD_LANGUAGE}')
                else:
                    for f in fields:
                        if f.value == 'ger':
                            f.value = 'de'
                        elif f.value == 'eng':
                            f.value = 'en'
                        else:
                            record_ok = False
                            errors.append(f'unexpected value for {DC_FIELD_LANGUAGE}: {f.value}')

        elif map_key == MARC21_DC_MAP_OES_JFM:
            pass

        return record_ok,errors

class DCField:
    tag: str
    value: str

    def __init__(self,tag,value):
        self.tag = tag
        self.value = value

    def __eq__(self, other):
        if isinstance(other, DCField):
            return self.tag == other.tag and self.value == other.value

        return False        
