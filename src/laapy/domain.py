from __future__ import annotations
import re
import decimal
from lxml import etree
from typing import TypeVar, List, Tuple

from collections import defaultdict

from .common import stripXmlDeclaration,addXmlDeclaration
from .marc import MarcRecord


def etree_to_dict(t):
    d = {t.tag: {} if t.attrib else None}
    children = list(t)
    if children:
        dd = defaultdict(list)
        for dc in map(etree_to_dict, children):
            for k, v in dc.items():
                dd[k].append(v)
        d = {t.tag: {k: v[0] if len(v) == 1 else v
                     for k, v in dd.items()}}
    if t.attrib:
        d[t.tag].update(('@' + k, v)
                        for k, v in t.attrib.items())
    if t.text:
        text = t.text.strip()
        if children or t.attrib:
            if text:
                d[t.tag]['#text'] = text
        else:
            d[t.tag] = text
    return d

class Base:
    ROOT_TAG = "***DUMMY***"
    FLAT_TAGS = []
    dont_mind_unknown_tags = True

    attribs_table = {}


    def __init__(self):
        self.xml = None
        self.unknown_tags = []
        for x in self.FLAT_TAGS:
            setattr(self,x,None)        

    def __str__(self):
        l = []
        for tag in self.FLAT_TAGS:
            l.append(tag+'='+str(getattr(self,tag,None)))
        s = '; '.join(l)
        s += '; unknown tags: '+str(self.unknown_tags)

        return s

    @classmethod
    def fromXml(cls: T, xml: str, dont_mind_unknown_tags: bool = None) -> T:
        return cls.fromNode(etree.fromstring(stripXmlDeclaration(xml)),dont_mind_unknown_tags=dont_mind_unknown_tags)

    @classmethod
    def fromNode(cls: T, root, dont_mind_unknown_tags: bool = None) -> T:
        if dont_mind_unknown_tags is None:
            dont_mind_unknown_tags = cls.dont_mind_unknown_tags
        x: T = cls.__new__(cls)
        x.__init__()
        x.xml = etree.tostring(root).decode("utf-8")
        children = root.getchildren()
        for child in children:
            if child.tag in cls.FLAT_TAGS or dont_mind_unknown_tags:
                setattr(x,child.tag,child.text)
                for k in child.keys():
                    v = child.get(k)
                    if v is not None:
                        if child.tag in cls.attribs_table:
                            pass
                        else:
                            cls.attribs_table[child.tag] = {}
                        cls.attribs_table[child.tag][k] = v
            else:
                x.unknown_tags.append(child.tag)

        if not dont_mind_unknown_tags and x.unknown_tags:
            raise Exception('unknown tags found for class {}: {}'.format(cls,",".join(x.unknown_tags)))
        return x

    @classmethod
    def multiFromXml(cls: T, xml:str, dont_mind_unknown_tags: bool = None ) -> List[T]:
        return cls.multiFromNode(etree.fromstring(stripXmlDeclaration(xml)),dont_mind_unknown_tags=dont_mind_unknown_tags)

    @classmethod
    def multiFromNode(cls: T, root, dont_mind_unknown_tags: bool = None ) -> List[T]:
        if dont_mind_unknown_tags is None:
            dont_mind_unknown_tags = cls.dont_mind_unknown_tags
        objects = []
        nl = root.findall('.//' + cls.ROOT_TAG)
        for node in nl:
            x = cls.fromNode(node,dont_mind_unknown_tags = dont_mind_unknown_tags)
            objects.append(x)

        return objects

    @classmethod
    def setTagValues(cls,xml,lookup):
        root = etree.fromstring(stripXmlDeclaration(xml))
        for k,v in lookup.items():
            node = root
            l = k.split('__')
            while len(l) > 1:
                sub = l.pop(0)
                node = node.find(sub)

            sub = l.pop(0)           
            el = node.find(sub)
            if el is not None:
                el.text = v
            else:
                el = etree.Element(k)
                el.text = v
                node.append(el)

        xml = etree.tostring(root, pretty_print=True).decode("utf-8") 

        return xml

T = TypeVar('T', bound = Base)
class SetMember(Base):
    ROOT_TAG = 'member'
    dont_mind_unknown_tags = True

    ATTR_LINK = 'link'
    TAG_ID = 'id'
    TAG_DESCRIPTION = 'description'

    FLAT_TAGS = [ATTR_LINK, TAG_ID, TAG_DESCRIPTION]

    def __init__(self):
        super().__init__()
        self.link = None

    @classmethod
    def multiFromXml(cls: T, xml:str, dont_mind_unknown_tags: bool = None ) -> List[T]:
        if dont_mind_unknown_tags is None:
            dont_mind_unknown_tags = cls.dont_mind_unknown_tags
        objects = []
        root = etree.fromstring(stripXmlDeclaration(xml))
        nl = root.findall('.//' + cls.ROOT_TAG)
        for node in nl:
            x = cls.fromNode(node,dont_mind_unknown_tags = dont_mind_unknown_tags)
            x.link = node.get(cls.ATTR_LINK)
            objects.append(x)

        return objects

class Set(Base):
    ROOT_TAG = 'set'
    dont_mind_unknown_tags = True

    TAG_LINK = 'link'
    TAG_ID = 'id'
    TAG_TYPE = 'type'
    TAG_CONTENT = 'content'
    TAG_NAME = 'name'

    FLAT_TAGS = [TAG_LINK, TAG_ID, TAG_TYPE, TAG_CONTENT, TAG_NAME]
class Request(Base):
    ROOT_TAG = 'user_request'
    dont_mind_unknown_tags = False

    TAG_ID = 'request_id'
    TAG_ADDITIONAL_ID = 'additional_id'
    TAG_MMS_ID = 'mms_id'
    TAG_TITLE = 'title'
    TAG_AUTHOR = 'author'
    TAG_MANAGED_BY_LIBRARY = 'managed_by_library'
    TAG_MANAGED_BY_LIBRARY_CODE = 'managed_by_library_code'
    TAG_MANAGED_BY_CIRCULATION_DESK = 'managed_by_circulation_desk'
    TAG_MANAGED_BY_CIRCULATION_DESK_CODE = 'managed_by_circulation_desk_code'
    TAG_TARGET_DESTINATION = 'target_destination'
    TAG_MATERIAL_TYPE = 'material_type'
    TAG_VOLUME = 'volume'
    TAG_ISSUE = 'issue'
    TAG_PART = 'part'
    TAG_DATE_OF_PUBLICATION = 'date_of_publication'
    TAG_REQUEST_TIME = 'request_time'
    TAG_TASK_NAME = 'task_name'
    TAG_EXPIRY_DATE = 'expiry_date'
    TAG_TYPE = 'request_type'
    TAG_SUBTYPE = 'request_sub_type'
    TAG_DATE = 'request_date'
    TAG_DESTINATION = 'destination'
    TAG_STATUS = 'request_status'
    TAG_ITEM_ID = 'item_id'
    TAG_BARCODE = 'barcode'
    TAG_PICKUP_LOCATION = 'pickup_location'
    TAG_PICKUP_LOCATION_LIBRARY = 'pickup_location_library'
    TAG_PICKUP_LOCATION_TYPE = 'pickup_location_type'
    TAG_USER_PRIMARY_ID = 'user_primary_id'
    TAG_DESTINATION_LOCATION = 'destination_location'
    TAG_CALL_NUMBER_TYPE = 'call_number_type'
    TAG_ITEM_POLICY = 'item_policy'
    TAG_REQUEST_TYPE = 'request_type'
    TAG_REQUEST_SUB_TYPE = 'request_sub_type'
    TAG_DESCRIPTION = 'description'
    TAG_PICKUP_LOCATION_CIRCULATION_DESK = 'pickup_location_circulation_desk'
    TAG_HOLDING_ID = 'holding_id'
    TAG_PLACE_IN_QUEUE = 'place_in_queue'
    TAG_COMMENT = 'comment'
    TAG_LAST_INTEREST_DATE = 'last_interest_date'

    FLAT_TAGS = [TAG_ID, TAG_ADDITIONAL_ID, TAG_MMS_ID, 
        TAG_TITLE, TAG_AUTHOR,
        TAG_MANAGED_BY_LIBRARY, TAG_MANAGED_BY_LIBRARY_CODE, TAG_MANAGED_BY_CIRCULATION_DESK, TAG_MANAGED_BY_CIRCULATION_DESK_CODE, TAG_TARGET_DESTINATION,
        TAG_MATERIAL_TYPE, TAG_VOLUME, TAG_ISSUE, TAG_PART, TAG_DATE_OF_PUBLICATION,
        TAG_REQUEST_TIME, TAG_TASK_NAME, TAG_EXPIRY_DATE,
        TAG_TYPE, TAG_SUBTYPE, TAG_DATE, TAG_DESTINATION, TAG_STATUS, TAG_ITEM_ID, TAG_BARCODE,
        TAG_PICKUP_LOCATION, TAG_PICKUP_LOCATION_LIBRARY, TAG_PICKUP_LOCATION_TYPE,
        TAG_USER_PRIMARY_ID, TAG_DESTINATION_LOCATION, TAG_CALL_NUMBER_TYPE, TAG_ITEM_POLICY,
        TAG_REQUEST_TYPE, TAG_REQUEST_SUB_TYPE, TAG_DESCRIPTION, TAG_PICKUP_LOCATION_CIRCULATION_DESK,
        TAG_HOLDING_ID, TAG_PLACE_IN_QUEUE, TAG_COMMENT, TAG_LAST_INTEREST_DATE
    ]

class Fee(Base):
    ROOT_TAG = 'fee'
    dont_mind_unknown_tags = False

    TAG_ID = 'id'
    TAG_TYPE = 'type'
    TAG_STATUS = 'status'
    TAG_USER_PRIMARY_ID = 'user_primary_id'
    TAG_BALANCE = 'balance'
    TAG_REMAINING_VAT_AMOUNT = 'remaining_vat_amount'
    TAG_ORIGINAL_AMOUNT = 'original_amount'
    TAG_ORIGINAL_VAT_AMOUNT = 'original_vat_amount'
    TAG_CREATION_TIME = 'creation_time'
    TAG_STATUS_TIME = 'status_time'
    TAG_COMMENT = 'comment'
    TAG_OWNER = 'owner'
    TAG_BARCODE = 'barcode'
    TAG_TITLE = 'title'
    TAG_BURSAR_TRANSACTION_ID = 'bursar_transaction_id'
    FLAT_TAGS = [
        TAG_ID,
        TAG_TYPE,
        TAG_STATUS,
        TAG_USER_PRIMARY_ID,
        TAG_BALANCE,
        TAG_REMAINING_VAT_AMOUNT,
        TAG_ORIGINAL_AMOUNT,
        TAG_ORIGINAL_VAT_AMOUNT,
        TAG_CREATION_TIME,
        TAG_STATUS_TIME,
        TAG_COMMENT,
        TAG_OWNER,
        TAG_BARCODE,
        TAG_TITLE,
    ]

    def __init__(self):
        super().__init__()
        self.transactions = []

    def __str__(self):
        s = super().__str__()
        for x in self.transactions:
            s += '; transaction: ' + str(x)    
        return s



    @classmethod
    def fromNode(cls: T, root, dont_mind_unknown_tags: bool = None) -> T:
        if dont_mind_unknown_tags is None:
            dont_mind_unknown_tags = cls.dont_mind_unknown_tags
        x: T = cls.__new__(cls)
        x.__init__()
        x.xml = etree.tostring(root).decode("utf-8")
        children = root.getchildren()
        for child in children:
            if child.tag == Transaction.MULTI_TAG:
                x.transactions = Transaction.multiFromNode(child)
            elif child.tag in cls.FLAT_TAGS or dont_mind_unknown_tags:
                setattr(x,child.tag,child.text)
                for k in child.keys():
                    v = child.get(k)
                    if v is not None:
                        if child.tag in cls.attribs_table:
                            pass
                        else:
                            cls.attribs_table[child.tag] = {}
                        cls.attribs_table[child.tag][k] = v
            else:
                x.unknown_tags.append(child.tag)

        if not dont_mind_unknown_tags and x.unknown_tags:
            raise Exception(f"unknown tag found for class {cls.__class__.__name__}, {x.unknown_tags}")

        return x

    def formattedBalance(self, digits=2):
        x = round(decimal.Decimal(self.balance),2)
        f = "{:10." + str(digits) + "f}"
        s = f.format(x)
        s = s.strip()

        return s
class Transaction(Base):
    MULTI_TAG = 'transactions'
    ROOT_TAG = 'transaction'
    dont_mind_unknown_tags = False

    TAG_ID = 'id'
    TAG_TYPE = 'type'
    TAG_AMOUNT ='amount'
    TAG_VAT_AMOUNT = 'vat_amount'
    TAG_CREATED_BY = 'created_by'
    TAG_EXTERNAL_TRANSACTION_ID = 'external_transaction_id'
    TAG_TRANSACTION_TIME = 'transaction_time'
    TAG_RECEIVED_BY = 'received_by'
    TAG_PAYMENT_METHOD = 'payment_method'
    TAG_REASON = 'reason'
    TAG_COMMENT = 'comment'

    FLAT_TAGS = [
        TAG_ID, TAG_TYPE, TAG_AMOUNT, TAG_VAT_AMOUNT, TAG_CREATED_BY, TAG_EXTERNAL_TRANSACTION_ID,
        TAG_TRANSACTION_TIME, TAG_RECEIVED_BY, TAG_PAYMENT_METHOD, TAG_REASON, TAG_COMMENT,
    ]        

class Bib(Base):
    ROOT_TAG = 'bib'
    dont_mind_unknown_tags = True

    RECORD_TAG = 'record'

    def __init__(self):
        super().__init__()
        self.record = None

    def __str__(self):
        s = super().__str__()
        s += '; record:' + str(self.record)

        return s

    @classmethod
    def fromNode(cls: T, root, dont_mind_unknown_tags: bool = None) -> T:
        if dont_mind_unknown_tags is None:
            dont_mind_unknown_tags = cls.dont_mind_unknown_tags
        x: T = cls.__new__(cls)
        x.__init__()
        children = root.getchildren()
        for child in children:
            if child.tag == cls.RECORD_TAG:
                x.record = MarcRecord()
                x.record.parseNode(child)
            elif child.tag in cls.FLAT_TAGS or dont_mind_unknown_tags:
                setattr(x,child.tag,child.text)
                for k in child.keys():
                    v = child.get(k)
                    if v is not None:
                        if child.tag in cls.attribs_table:
                            pass
                        else:
                            cls.attribs_table[child.tag] = {}
                        cls.attribs_table[child.tag][k] = v
            else:
                x.unknown_tags.append(child.tag)

        return x
    
class Holding(Base):
    ROOT_TAG = 'holding'
    dont_mind_unknown_tags = True

    RECORD_TAG = 'record'

    record: MarcRecord

    def __init__(self):
        super().__init__()
        self.record = None

    def __str__(self):
        s = super().__str__()
        s += '; record:' 
        s += str(self.record) if self.record else '---'

        return s

    @classmethod
    def fromNode(cls: T, root, dont_mind_unknown_tags: bool = None) -> T:
        if dont_mind_unknown_tags is None:
            dont_mind_unknown_tags = cls.dont_mind_unknown_tags
        x: T = cls.__new__(cls)
        x.__init__()
        x.xml = etree.tostring(root).decode("utf-8")
        children = root.getchildren()
        for child in children:
            if child.tag == cls.RECORD_TAG:
                x.record = MarcRecord()
                x.record.parseNode(child)
            elif child.tag in cls.FLAT_TAGS or dont_mind_unknown_tags:
                setattr(x,child.tag,child.text)
                for k in child.keys():
                    v = child.get(k)
                    if v is not None:
                        if child.tag in cls.attribs_table:
                            pass
                        else:
                            cls.attribs_table[child.tag] = {}
                        cls.attribs_table[child.tag][k] = v
            else:
                x.unknown_tags.append(child.tag)

        if not dont_mind_unknown_tags and x.unknown_tags:
            raise Exception(f"unknown tag found for class {cls.__class__.__name__}")

        return x

    @classmethod
    def multiFromXml(cls: T, xml:str, dont_mind_unknown_tags: bool = None ) -> List[T]:
        if dont_mind_unknown_tags is None:
            dont_mind_unknown_tags = cls.dont_mind_unknown_tags
        objects = []
        root = etree.fromstring(stripXmlDeclaration(xml))
        nl = root.findall('.//' + cls.ROOT_TAG)
        for node in nl:
            x = cls.fromNode(node,dont_mind_unknown_tags = dont_mind_unknown_tags)
            objects.append(x)

        return objects


class ItemData(Base):
    ROOT_TAG = 'item_data'
    dont_mind_unknown_tags = True

    TAG_LIBRARY = 'library'
    TAG_LOCATION = 'location'
    TAG_BARCODE = 'barcode'
    TAG_INTERNAL_NOTE_1 = 'internal_note_1'
    TAG_INTERNAL_NOTE_2 = 'internal_note_2'
    TAG_INTERNAL_NOTE_3 = 'internal_note_3'

class BibData(Base):
    ROOT_TAG = 'bib_data'
    dont_mind_unknown_tags = True

    TAG_TITLE = 'title'
    TAG_AUTHOR = 'author'

class HoldingData(Base):
    ROOT_TAG = 'holding_data'
    dont_mind_unknown_tags = True

    TAG_TEMP_LIBRARY = 'temp_library'
    TAG_TEMP_LOCATION = 'temp_location'
    TAG_IN_TEMP_LOCATION = 'in_temp_location'

    FLAT_TAGS = [
        TAG_TEMP_LIBRARY, TAG_TEMP_LOCATION
    ]        
class Item(Base):
    ROOT_TAG = 'item'
    dont_mind_unknown_tags = True
    
    def __init__(self):
        super().__init__()
        self.bib_data = None
        self.holding_data = None
        self.item_data = None

    def __str__(self):
        s = super().__str__()
        s += '; bib_data: ' + str(self.bib_data)
        s += '; holding_data: ' + str(self.holding_data)
        s += '; item_data: ' + str(self.item_data)
        return s

    @classmethod
    def splitLink(cls: T,link: str) -> Tuple[str,str,str]:
        match = re.search(r'/bibs/(\d+)',link); mmsid = match[1]
        match = re.search(r'/holdings/(\d+)',link); holid = match[1]
        match = re.search(r'/items/(\d+)',link); itemid = match[1]
        return mmsid, holid, itemid

    @classmethod
    def fromNode(cls: T, root, dont_mind_unknown_tags: bool = None) -> T:
        if dont_mind_unknown_tags is None:
            dont_mind_unknown_tags = cls.dont_mind_unknown_tags
        x: T = cls.__new__(cls)
        x.__init__()
        x.xml = etree.tostring(root).decode("utf-8")
        children = root.getchildren()
        for child in children:
            if child.tag == BibData.ROOT_TAG:
                x.bib_data = BibData.fromNode(child)
            elif child.tag == HoldingData.ROOT_TAG:
                x.holding_data = HoldingData.fromNode(child)
            elif child.tag == ItemData.ROOT_TAG:
                x.item_data = ItemData.fromNode(child)
            elif child.tag in cls.FLAT_TAGS or dont_mind_unknown_tags:
                setattr(x,child.tag,child.text)
                for k in child.keys():
                    v = child.get(k)
                    if v is not None:
                        if child.tag in cls.attribs_table:
                            pass
                        else:
                            cls.attribs_table[child.tag] = {}
                        cls.attribs_table[child.tag][k] = v
            else:
                x.unknown_tags.append(child.tag)

        if not dont_mind_unknown_tags and x.unknown_tags:
            raise Exception(f"unknown tag found for class {cls.__class__.__name__}")

        return x

class User(Base):
    ROOT_TAG = 'user'
    dont_mind_unknown_tags = True

    TAG_PRIMARY_ID = 'primary_id'
    TAG_FIRST_NAME = 'first_name'
    TAG_LAST_NAME = 'last_name'
    TAG_FULL_NAME = 'full_name'
    TAG_USER_GROUP = 'user_group'
    TAG_PREFERRED_LANGUAGE = 'preferred_language'
    TAG_EXPIRY_DATE = 'expiry_date'
    TAG_EMAIL_ADDRESS = 'email_address'

    def __init__(self):
        super().__init__()
        self.primary_id = ''
        self.first_name = ''
        self.last_name = ''
        self.user_group = ''
        self.expiry_date = ''

class Loan(Base):
    ROOT_TAG = 'item_loan'
    dont_mind_unknown_tags = True

class Letter(Base):
#<letter link="https://api-eu.hosted.exlibrisgroup.com/almaws/v1/conf/letters/AnalyticsLetter">
#    <code>AnalyticsLetter</code>
#    <enabled desc="Yes">true</enabled>
#    <name>Analytics Letter</name>
#    <description>Analytics Letter</description>
#    <channel>EMAIL</channel>
#    <retention_period/>
#    <customized desc="Yes">true</customized>
#    <patron_facing desc="No">false</patron_facing>
#    <updated_by>TUWSCH</updated_by>
#    <update_date>2017-10-02Z</update_date>
#    <labels link="https://api-eu.hosted.exlibrisgroup.com/almaws/v1/conf/code-tables/AnalyticsLetter">AnalyticsLetter</labels>
#  </letter>
  
    ROOT_TAG = 'letter'
    dont_mind_unknown_tags = True

    TAG_CODE = 'code'
    TAG_ENABLED = 'desc'
    TAG_NAME = 'name'
    TAG_DESCRIPTION = 'description'
    TAG_CHANNEL = 'channel'
    TAG_RETENTION_PERIOD = 'retenntion_period'
    TAG_CUSTOMIZED = 'customized'
    TAG_PATRON_FACING = 'patron_facing'
    TAG_UPDATED_BY = 'updated_by'
    TAG_UPDATE_DATE = 'update_date'
    TAG_LABELS = 'labels'

    FLAT_TAGS = [TAG_CODE, TAG_ENABLED, TAG_NAME, 
        TAG_DESCRIPTION, TAG_CHANNEL, TAG_RETENTION_PERIOD,
        TAG_CUSTOMIZED, TAG_PATRON_FACING, TAG_UPDATED_BY, TAG_UPDATE_DATE, TAG_LABELS,
        ]

    def __init__(self):
        super().__init__()

if __name__ == '__main__':
    xml = '''
    <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <letters total_record_count="134">
    <letter link="https://api-eu.hosted.exlibrisgroup.com/almaws/v1/conf/letters/AnalyticsLetter">
        <code>AnalyticsLetter</code>
        <enabled desc="Yes">true</enabled>
        <name>Analytics Letter</name>
        <description>Analytics Letter</description>
        <channel>EMAIL</channel>
        <retention_period/>
        <customized desc="Yes">true</customized>
        <patron_facing desc="No">false</patron_facing>
        <updated_by>TUWSCH</updated_by>
        <update_date>2017-10-02Z</update_date>
        <labels link="https://api-eu.hosted.exlibrisgroup.com/almaws/v1/conf/code-tables/AnalyticsLetter">AnalyticsLetter</labels>
    </letter>
    <letter link="https://api-eu.hosted.exlibrisgroup.com/almaws/v1/conf/letters/BorrowerClaimEmailLetter">
        <code>BorrowerClaimEmailLetter</code>
        <enabled desc="Yes">true</enabled>
        <name>Borrower Claim Email Letter</name>
        <description>Borrower Claim Email Letter</description>
        <channel>EMAIL</channel>
        <retention_period/>
        <customized desc="No">false</customized>
        <patron_facing desc="Yes">true</patron_facing>
        <updated_by/>
        <labels link="https://api-eu.hosted.exlibrisgroup.com/almaws/v1/conf/code-tables/BorrowerClaimEmailLetter">BorrowerClaimEmailLetter</labels>
    </letter> 
    </letters>'''

    objects = Letter.multiFromXml(xml)
    for x in objects:
        print (x.xml)



class Portfolio(Base):
    ROOT_TAG = 'portfolio'
    dont_mind_unknown_tags = True


    def __init__(self):
        super().__init__()

    def __str__(self):
        s = super().__str__()

        return s

    @classmethod
    def fromNode(cls: T, root, dont_mind_unknown_tags: bool = None) -> T:
        if dont_mind_unknown_tags is None:
            dont_mind_unknown_tags = cls.dont_mind_unknown_tags
        x: T = cls.__new__(cls)
        x.__init__()
        x.xml = etree.tostring(root).decode("utf-8")
        children = root.getchildren()
        for child in children:
            if child.tag in cls.FLAT_TAGS:
                setattr(x,child.tag,child.text)
                for k in child.keys():
                    v = child.get(k)
                    if v is not None:
                        if child.tag in cls.attribs_table:
                            pass
                        else:
                            cls.attribs_table[child.tag] = {}
                        cls.attribs_table[child.tag][k] = v
            elif dont_mind_unknown_tags:
                v = etree_to_dict(child)
                setattr(x,child.tag,v.get(child.tag))
            else:
                x.unknown_tags.append(child.tag)

        if not dont_mind_unknown_tags and x.unknown_tags:
            raise Exception(f"unknown tag found for class {cls.__class__.__name__}")

        return x

    @classmethod
    def multiFromXml(cls: T, xml:str, dont_mind_unknown_tags: bool = None ) -> List[T]:
        if dont_mind_unknown_tags is None:
            dont_mind_unknown_tags = cls.dont_mind_unknown_tags
        objects = []
        root = etree.fromstring(stripXmlDeclaration(xml))
        nl = root.findall('.//' + cls.ROOT_TAG)
        for node in nl:
            x = cls.fromNode(node,dont_mind_unknown_tags = dont_mind_unknown_tags)
            objects.append(x)

        return objects

