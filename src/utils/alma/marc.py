import lxml
from lxml import etree

class MarcRecord:

    def __init__(self):
        leader=None
        controlfields=None
        datafields=None

    def parse(self,xml):
        root=etree.fromstring(xml)
        self.controlfields=[]
        self.datafields=[]
        self.leader=root.findall('leader')[0].text
        nl_cfield=root.findall('controlfield')
        for node_cfield in nl_cfield:
            cfield=ControlField()
            cfield.value=node_cfield.text
            cfield.tag=node_cfield.attrib['tag']
            self.controlfields.append(cfield)
        nl_dfield=root.findall('datafield')
        for node_dfield in nl_dfield:
            dfield=DataField()
            dfield.value=node_dfield.text
            dfield.tag=node_dfield.attrib['tag']
            dfield.ind1=node_dfield.attrib['ind1']
            dfield.ind2=node_dfield.attrib['ind2']
            dfield.subfields=[]
            self.datafields.append(dfield)
            nl_subfield=node_dfield.findall('subfield')
            for node_subfield in nl_subfield:
                subfield=Subfield()
                subfield.value=node_subfield.text
                subfield.code=node_subfield.attrib['code']
                dfield.subfields.append(subfield)

    def getControlFieldsForTag(self,tag):
        matchingfields=[]
	
        for cf in self.controlfields:
            if cf.tag==tag:
                matchingfields.append(cf)

        return matchingfields


    def getDataFieldsForTag(self,tag,ind1,ind2):
        matchingfields=[]
        
        for df in self.datafields:
            if df.tag!=tag:
                continue

            if ind1!='-' and ind1!=df.ind1:
                continue
            
            if ind2!='-' and ind2!=df.ind2:
                continue
            
            matchingfields.append(df)
        
        return matchingfields
    

    def getMMSId(self):
	    return self.getControlFieldsForTag('001')[0].value

    def getAC(self):
	    return self.getControlFieldsForTag('009')[0].value

    def getTitle(self):
        str=None

        datafields=self.getDataFieldsForTag('245','0','0');
        datafield=datafields[0]

        if datafield is not None:
            subfields=datafield.subfields
            for subfield in subfields:
                if subfield.code=='a':
                    str=subfield.value
        else:
            datafields=self.getDataFieldsForTag('245','-','-');
            datafield=datafields[0]
            if datafield is not None:
                subfields=datafield.subfields
                for subfield in subfields:
                    if subfield.code=='a':
                        str=subfield.value
        
        return str

    def getAuthor(self):
        str=None

        datafields=self.getDataFieldsForTag('100','1','-')
        datafield=datafields[0]

        if datafield is not None:
            subfields=datafield.subfields
            for subfield in subfields:
                if subfield.code=='a':
                    str=subfield.value
        else:
            datafields=self.getDataFieldsForTag('700','1','-')
            datafield=datafields[0]
            if datafield is not None:
                subfields=datafield.subfields
                for subfield in subfields:
                    if subfield.code=='a':
                        str=subfield.value
        
        return str


    def getYear(self):
        str=None

        datafields=self.getDataFieldsForTag('264',' ','1')
        datafield=datafields[0]

        if datafield is not None:
            subfields=datafield.subfields
            for subfield in subfields:
                if subfield.code=='c':
                    str=subfield.value
        return str

    def debug(self):
        print("leader = "+self.leader)

    def toXML(self):
        xml=''
        xml+='<record>'
        xml+='<leader>'+self.leader+'</leader>'    
        for datafield in self.datafields:
            xml+='<datafield '
            xml+='tag="'+datafield.tag+""' '
            xml+='ind1="'+datafield.ind1+'" '
            xml+='ind2="'+datafield.ind2+'">'
            for subfield in datafield.subfields:
                xml+='<subfield code="'
                xml+=subfield.code+'">'
                xml+=subfield.value
                xml+='</subfield>'
            xml+='</datafield>'
        xml+='</record>'

class ControlField:

    tag=None
    value=None

class DataField:

    tag=None
    ind1=None
    ind2=None
    subfields=[]

    def __init__(self,tag,ind1,ind2):
        self.tag=tag
        self.ind1=ind1
        self.ind2=ind2

    def addSubfield(self,subfield):
        self.subfields.append(subfield)

class Subfield:

    code=None
    value=None

    def __init__(self,code,value):
        self.code=code
        self.value=value


text="""
<record>
    <leader>01876nas#a2200529#c#4500</leader>
    <controlfield tag="001">990006498190203336</controlfield>
    <controlfield tag="005">20170724210100.0</controlfield>
    <controlfield tag="007">cr#|||||||||||</controlfield>
    <controlfield tag="008">000707|19949999xxk#|#p#######|####|eng#u</controlfield>
    <controlfield tag="009"></controlfield>
    <datafield ind1="7" tag="016" ind2=" ">
        <subfield code="a">020567944</subfield>
        <subfield code="2">DE-101b</subfield>
    </datafield>
    <datafield ind2=" " tag="016" ind1="7">
        <subfield code="a">2018371-9</subfield>
        <subfield code="2">DE-600</subfield>
    </datafield>
</record>
"""
mr=MarcRecord()
mr.parse(text)
mr.debug()