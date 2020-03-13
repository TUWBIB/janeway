import lxml
from lxml import etree

class MarcRecord:
    def __init__(self):
        self.leader=None
        self.controlfields=[]
        self.datafields=[]

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
                subfield=SubField()
                subfield.value=node_subfield.text
                subfield.code=node_subfield.attrib['code']
                dfield.subfields.append(subfield)

    def addDataField(self,df):
        self.datafields.append(df)
    
    def addControlField(self,cf):
        self.controlfields.append(cf)

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
            xml+='tag="'+datafield.tag+'" '
            xml+='ind1="'+datafield.ind1+'" '
            xml+='ind2="'+datafield.ind2+'">'
            for subfield in datafield.subfields:
                xml+='<subfield code="'
                xml+=subfield.code+'">'
                xml+=subfield.value
                xml+='</subfield>'
            xml+='</datafield>'
        xml+='</record>'

        return xml

class ControlField:
    def __init__(self):
        self.tag=None
        self.value=None

    @classmethod
    def createControlField(cls,tag,value):
        cf=DataField()
        cf.tag=tag
        cf.value=value
        return cf

class DataField:
    def __init__(self):
        self.tag=None
        self.ind1=None
        self.ind2=None
        self.subfields=[]

    @classmethod
    def createDataField(cls,tag,ind1,ind2):
        df=DataField()
        df.tag=tag
        df.ind1=ind1
        df.ind2=ind2
        return df

    def addSubfield(self,subfield):
        self.subfields.append(subfield)

class SubField:
    def __init__(self):
        self.code=None
        self.value=None

    @classmethod
    def createSubfield(cls,code,value):
        sf=SubField()
        sf.code=code
        sf.value=value
        return sf
