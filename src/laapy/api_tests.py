# PYTHON_ARGCOMPLETE_OK

# python3 api_tests.py get_item sandbox --mmsid 990007296920203336 --holid 2240512920003336 --itemid 2340512860003336
# python3 api_tests.py update_item sandbox --mmsid 990007296920203336 --holid 2240512920003336 --itemid 2340512860003336
# python3 api/api_tests.py create_item sandbox --mmsid 990007296920203336 --holid 2240512920003336
# python3 api_tests.py delete_item sandbox --mmsid 990007296920203336 --holid 2240512920003336 --itemid 23106184980003336
# python3 api/api_tests.py update_item_tag_values  sandbox --barcode +EM73494706 --urlparams temp_location=ZADJ,temp_library=EHB
# python3 laapy/api_tests.py update_user_tag_values sandbox --userid ZPAT1 --urlparams "purge_date=1994-05-04"
# python3 laapy/api_tests.py create_set sandbox --urlparams "name=items_2602x,type=LOGICAL,content=ITEM,private=false,query=ITEM where HOLDING ((permanentPhysicalLocation OUTER_EQUAL ((E260 : 2602))) AND ITEM (arrivalDate BEFORE \"2022-08-05\"))"
# python3 laapy/api_tests.py get_items sandbox --mmsid 990002375180203336 --holid 2244358760003336
# python3 laapy/api_tests.py get_bib sandbox --mmsid 990002375180203336
# python3 laapy/api_tests.py get_holdings sandbox --mmsid 990002375180203336
# python3 laapy/api_tests.py get_analytics_report production --urlparams "path=/shared/Technische Universität Wien/Reports/API/LOAN_LIST,limit=25"




import traceback
import argparse
import argcomplete
import sys
import os
import re
import threading
import time
from lxml import etree
from bs4 import BeautifulSoup

head,tail=os.path.split(sys.path[0])
x = head
if x not in sys.path: sys.path.append(x)
x = os.path.join(head,tail)
if x not in sys.path: sys.path.append(x)
print(sys.path)

from laapy import addXmlDeclaration,stripXmlDeclaration, prettyPrint
from laapy.api import API,APIThread,APIResult
from laapy.domain import Item, ItemData, Set, SetMember, Fee, Transaction, Request, Holding, User, Loan, Letter

from laapy.marc import MarcRecord, ControlField, DataField, SubField
from laapy.tasks_common import *

TEST_PRINT_CONFIG = 'print_config'
TEST_GET = 'get'
TEST_CREATE_BIB = 'create_bib'
TEST_UPDATE_BIB = 'update_bib'
TEST_CREATE_SET = 'create_set'
TEST_DELETE_SET = 'delete_set'
TEST_GET_SET = 'get_set'
TEST_FIND_SET_BY_NAME = 'find_set_by_name'
TEST_SET_MEMBERS = 'fetch_set_members'
TEST_SET_MEMBERS_MT = 'fetch_set_members_mt'
TEST_SET_EXTEND = 'extend_set'
TEST_SET_ADD_MMSID ='set_add_mmsid'
TEST_GET_BIB = 'get_bib'
TEST_GET_HOLDING = 'get_holding'
TEST_SUPPRESS_HOLDING = 'suppress_holding'
TEST_GET_HOLDINGS = 'get_holdings'
TEST_CREATE_HOLDING = 'create_holding'
TEST_GET_ITEM = 'get_item'
TEST_GET_ITEM_VIA_BARCODE = 'get_item_via_barcode'
TEST_UPDATE_ITEM = 'update_item'
TEST_DELETE_ITEM = 'delete_item'
TEST_CREATE_ITEM = 'create_item'
TEST_GET_ITEMS = 'get_items'
TEST_GET_ITEMCOUNT = 'get_itemcount'
TEST_UPDATE_ITEM_TAG_VALUES = 'update_item_tag_values'
TEST_CHANGE_ITEMS_JOB ='change_items_job'
TEST_RESOLVE_BARCODE = 'resolve_barcode'
TEST_GET_USER = 'get_user'
TEST_CREATE_USER = 'create_user'
TEST_DELETE_USER = 'delete_user'
TEST_UPDATE_USER_TAG_VALUES = 'update_user_tag_values'
TEST_GET_USER_LOANS = 'get_user_loans'
TEST_GET_USER_FEES = 'get_user_fees'
TEST_PAY_USER_FEE = 'pay_user_fee'
TEST_WAIVE_USER_FEE = 'waive_user_fee'
TEST_OP_USER_FEE = 'op_user_fee'
TEST_LIST_REQUESTS = 'list_requests'
TEST_GET_REQUEST = 'get_request'
TEST_DELETE_REQUEST = 'delete_request'
TEST_MARC_TO_DC = 'marc_to_dc'
TEST_RDF_GET_WORK = 'rdf_get_work'
TEST_RDF_GET_MANIFESTATION = 'rdf_get_manifestation'
TEST_GET_LETTERS = 'get_letters'
TEST_HARCODED = 'test_hardcoded'
TEST_GET_ANALYTICS_PATHS = 'get_analytics_paths'
TEST_GET_ANALYTICS_REPORT = 'get_analytics_report'
TEST_CREATE_PORTFOLIO = 'create_portfolio'
TEST_GET_PORTFOLIOS = 'get_portfolios'
TEST_GET_PORTFOLIO = 'get_portfolio'
TEST_DELETE_PORTFOLIO = 'delete_porfolio'
TEST_SRU = 'test_sru'
TEST_GET_REQUESTED_RESOURCES = 'get_requested_resources'

TESTS = [
    TEST_PRINT_CONFIG,
    TEST_GET,
    TEST_GET_BIB, TEST_CREATE_BIB, TEST_UPDATE_BIB,
    TEST_CREATE_SET, TEST_DELETE_SET, TEST_GET_SET, TEST_SET_ADD_MMSID,
    TEST_FIND_SET_BY_NAME, TEST_SET_MEMBERS, TEST_SET_MEMBERS_MT, TEST_SET_EXTEND,
    TEST_GET_HOLDING, TEST_SUPPRESS_HOLDING, TEST_CREATE_HOLDING, TEST_GET_HOLDINGS,
    TEST_GET_ITEM, TEST_GET_ITEM_VIA_BARCODE, TEST_GET_ITEMCOUNT, TEST_CREATE_ITEM, TEST_UPDATE_ITEM, TEST_GET_ITEMS, TEST_DELETE_ITEM,TEST_RESOLVE_BARCODE, TEST_UPDATE_ITEM_TAG_VALUES, TEST_CHANGE_ITEMS_JOB, 
    TEST_GET_USER, TEST_UPDATE_USER_TAG_VALUES, TEST_GET_USER_LOANS, TEST_GET_USER_FEES, TEST_PAY_USER_FEE, TEST_WAIVE_USER_FEE, TEST_OP_USER_FEE,
    TEST_LIST_REQUESTS, TEST_GET_REQUEST, TEST_DELETE_REQUEST,
    TEST_CREATE_USER, TEST_DELETE_USER,
    TEST_MARC_TO_DC,
    TEST_RDF_GET_WORK,TEST_RDF_GET_MANIFESTATION,
    TEST_GET_LETTERS,
    TEST_HARCODED,
    TEST_GET_ANALYTICS_PATHS,TEST_GET_ANALYTICS_REPORT,
    TEST_CREATE_PORTFOLIO,TEST_GET_PORTFOLIOS, TEST_GET_PORTFOLIO, TEST_DELETE_PORTFOLIO,
    TEST_SRU,
    TEST_GET_REQUESTED_RESOURCES,
    ]

API_TARGET_SANDBOX = 'sandbox'
API_TARGET_PRODUCTION = 'production'
API_TARGETS = [API_TARGET_SANDBOX, API_TARGET_PRODUCTION]
api_target = None

def test_create_bib():
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<bib>
  <record>
    <leader>02696naa a2200325 c 4500</leader>
    <controlfield tag="001">997754350303336</controlfield>
    <controlfield tag="005">20201214112231.0</controlfield>
    <controlfield tag="007">cr#|||||||||||</controlfield>
    <controlfield tag="008">201214|2020    |||     o     ||| 0 ger c</controlfield>
    <controlfield tag="009">AC16106595</controlfield>
    <datafield ind1="7" ind2=" " tag="024">
      <subfield code="a">10.34749/oes.2020.4583</subfield>
      <subfield code="2">doi</subfield>
    </datafield>
    <datafield ind1=" " ind2=" " tag="035">
      <subfield code="a">(AT-OBV)AC16106595</subfield>
    </datafield>
    <datafield ind1=" " ind2=" " tag="035">
      <subfield code="a">(DE-599)OBVAC16106595</subfield>
    </datafield>
    <datafield ind1=" " ind2=" " tag="035">
      <subfield code="a">(EXLNZ-43ACC_NETWORK)99145776368903331</subfield>
    </datafield>
    <datafield ind1=" " ind2=" " tag="040">
      <subfield code="a">TUW</subfield>
      <subfield code="b">ger</subfield>
      <subfield code="c">JW</subfield>
      <subfield code="d">AT-UBTUW</subfield>
      <subfield code="e">rda</subfield>
    </datafield>
    <datafield ind1=" " ind2=" " tag="041">
      <subfield code="a">ger</subfield>
    </datafield>
    <datafield ind1=" " ind2=" " tag="044">
      <subfield code="a">XA-AT</subfield>
    </datafield>
    <datafield ind1="1" ind2=" " tag="100">
      <subfield code="a">Zink, Lukas</subfield>
      <subfield code="4">aut</subfield>
      <subfield code="4">oth</subfield>
      <subfield code="e">Corresponding author</subfield>
    </datafield>
    <datafield ind1="1" ind2="0" tag="245">
      <subfield code="a">Handels- und infrastrukturpolitische Herausforderungen des europäischen Gasmarkts</subfield>
      <subfield code="b">mit räumlichem Fokus auf Osteuropa</subfield>
      <subfield code="c">Lukas Zink</subfield>
    </datafield>
    <datafield ind1=" " ind2=" " tag="251">
      <subfield code="a">vor</subfield>
      <subfield code="2">coar</subfield>
    </datafield>
    <datafield ind1=" " ind2="1" tag="264">
      <subfield code="a">Wien</subfield>
      <subfield code="b">Technische Universität Wien</subfield>
      <subfield code="c">2020</subfield>
    </datafield>
    <datafield ind1=" " ind2=" " tag="300">
      <subfield code="a">Online-Ressource (15 Seiten)</subfield>
      <subfield code="b">Illustrationen, Diagramme</subfield>
    </datafield>
    <datafield ind1=" " ind2=" " tag="336">
      <subfield code="b">txt</subfield>
    </datafield>
    <datafield ind1=" " ind2=" " tag="337">
      <subfield code="b">c</subfield>
    </datafield>
    <datafield ind1=" " ind2=" " tag="338">
      <subfield code="b">cr</subfield>
    </datafield>
    <datafield ind1=" " ind2=" " tag="347">
      <subfield code="a">Textdatei</subfield>
      <subfield code="b">PDF</subfield>
    </datafield>
    <datafield ind1=" " ind2=" " tag="500">
      <subfield code="a">Refereed/Peer-reviewed</subfield>
    </datafield>
    <datafield ind1="0" ind2=" " tag="506">
      <subfield code="a">Open Access</subfield>
      <subfield code="f">Unrestricted online access</subfield>
      <subfield code="2">star</subfield>
    </datafield>
    <datafield ind1=" " ind2=" " tag="520">
      <subfield code="a">ger: Der europäische Raum ist aufgrund seines geringen Vorkommens des essentiellen Wirtschaftsgutes Erdgas eine sehr attraktive Nachfrageregion. Aktuelle umweltorientierte Maßnahmen auf Ebene der EU veranlassen Europa zur Senkung der Produktion fossiler Energien, wodurch der Import über Erdgas-Versorgungskorridore immer wichtiger wird. Diese Korridore fungieren jedoch auch als Wirtschaftskorridore, die einen maßgeblichen Einfluss auf die umliegenden Räume bzw. Regionen haben. Aktuelle Entwicklungen verändern die bestehende Versorgungsstruktur. Auf Basis einer Analyse des europäischen Gasmarkts wurden drei Gastransportregionen mit nahezu gleichartigen Herausforderungen und Chancen identifiziert. Alle sind im Bereich Energieversorgung von nur einem Anbieter - Russland - abhängig. Das Ziel, die wirtschaftliche Abhängigkeit von Russlands Energie-Exporten aufzubrechen kann erfolgreich sein, ist jedoch mit Herausforderungen verbunden. Die Wahl liegt dabei zwischen einer sicheren und billigen jedoch abhängigen Energiewirtschaft oder einer ungewissen Energieautarkie. Dies bietet für osteuropäische Staaten (Estland, Lettland, Litauen, Finnland, Weißrussland, Ukraine, Slowakei, Ungarn, Bulgarien und Rumänien) eine Option, die eigene Relevanz als wirtschaftlich bedeutender Raum im Bereich Energietransport zu steigern.</subfield>
    </datafield>
    <datafield ind1=" " ind2=" " tag="542">
      <subfield code="a">Unter einer CC-Lizenz, Details siehe Link</subfield>
      <subfield code="f">CC BY-NC 4.0</subfield>
      <subfield code="2">cc</subfield>
      <subfield code="u">https://creativecommons.org/licenses/by-nc/4.0</subfield>
    </datafield>
    <datafield ind1="0" ind2="8" tag="773">
      <subfield code="i">Enthalten in</subfield>
      <subfield code="t">Der Öffentliche Sektor - The Public Sector</subfield>
      <subfield code="d">2020</subfield>
      <subfield code="g">Jahrgang 46 (2020), Heft 2, Seiten 67-81</subfield>
      <subfield code="w">(AT-OBV)AC10863779</subfield>
    </datafield>
    <datafield ind1="4" ind2="0" tag="856">
      <subfield code="q">text/html</subfield>
      <subfield code="u">https://doi.org/10.34749/oes.2020.4583</subfield>
      <subfield code="x">TUW</subfield>
      <subfield code="z">kostenfrei</subfield>
      <subfield code="3">Volltext</subfield>
    </datafield>
    <datafield ind1="2" ind2=" " tag="970">
      <subfield code="a">TUW</subfield>
      <subfield code="d">OA-ARTICLE</subfield>
    </datafield>
    <datafield ind1="3" ind2="3" tag="996">
      <subfield code="a">Gold Open Access ; Journal Hosting System</subfield>
      <subfield code="9">local</subfield>
    </datafield>
  </record>
</bib>
"""
    result = api.createBibRecord(xml,unsuppress=False)
    xml = result.data
    errs = result.errs
    if errs:
        raise Exception(*errs)

    print(xml)

def test_get_bib(mmsid):
    result = api.getBibRecord(mmsid)
    xml = result.data
    errs = result.errs
    if errs:
        raise Exception(*errs)

    print(xml)


def test_update_bib(mmsid):
    mr: MarcRecord
    result = api.getBibRecord(mmsid)
    xml = result.data
    errs = result.errs
    if errs:
        raise Exception(*errs)

    xml = stripXmlDeclaration(xml)
    mr = MarcRecord()
    mr.parse(xml)
    f = DataField.createDataField(tag = '983', ind1=' ', ind2=' ')
    f.addSubField(SubField.createSubField('a','test'))    
    f.addSubField(SubField.createSubField('9','local'))
    mr.addDataField(f)

    xml = mr.toBibXML()
    result = api.updateBibRecord(xml,mmsid)
    xml = result.data
    errs = result.errs
    if errs:
        raise Exception(*errs)



def test_get_holding(mmsid, holid):
    result = api.getHoldingRecord(mmsid, holid)
    xml = result.data
    errs = result.errs
    if errs:
        raise Exception(*errs)

    holding = Holding.fromXml(xml)
    print(holding)
    print(xml)

def test_suppress_holding(mmsid,holid,flags):
    print(flags)
    suppress = flags.get(FLAG_SUPPRESS,None)
    if not suppress:
        print("suppress flag with value true or false expected")
        exit(1)
    if suppress != 'true' and suppress !='false':
        print("suppress flag with value true or false expected")
        exit(1)
    suppress = True if suppress == 'true' else False
    result = api.holSuppress(mmsid,holid,suppress)
    xml = result.data
    errs = result.errs
    if errs:
        raise Exception(*errs)

def test_get_holdings(mmsid):
    holdings, result = api.getHoldings(mmsid)
    if result and result.errs:
        raise Exception(*result.errs)

    print('number of holdings:', len(holdings))
    for holding in holdings:
        print(holding.holding_id)
        print(holding.library)
        print(holding.location)

def test_create_holding(mmsid):
    mr = MarcRecord()
    mr.leader = '^^^^^nx^^a22^^^^^1i^4500'
    df = DataField.createDataField('852','8','1')
    df.addSubField(SubField.createSubField('b','EHB'))
    df.addSubField(SubField.createSubField('c','9200'))
    mr.addDataField(df)
    xml = mr.toHoldingXML()

    result = api.createHoldingRecord(mmsid, xml)
    xml = result.data
    errs = result.errs
    if errs:
        raise Exception(*errs)

    print(xml)

def test_get_item(mmsid, holid, itemid):
    result = api.getItem(mmsid, holid, itemid)
    xml = result.data
    errs = result.errs
    if errs:
        raise Exception(*errs)

    item = Item.fromXml(xml)
    print(item)
    print(xml)

def test_get_item_via_barcode(barcode):
    item_not_found, mmsid, holid, itemid, result = api.resolveBarcode(barcode)

    errs = result.errs
    if errs:
        raise Exception(*errs)

    if item_not_found:
        print(f"no item with barcode {barcode}")
    else:
        test_get_item(mmsid,holid,itemid)


def test_get_items(mmsid, holid):
    kwargs = {}
    if OPTIONS[OP_LIMIT]: kwargs['limit'] = OPTIONS[OP_LIMIT]
    if OPTIONS[OP_OFFSET]: kwargs['offset'] = OPTIONS[OP_OFFSET]
    items, result = api.getItems(mmsid, holid, **kwargs)
    if result and result.errs:
        raise Exception(*result.errs)

    print('Number of items:', len(items))
    for item in items:
        print(item.item_data.barcode)

def test_get_itemcount(mmsid, holid):
    itemcount, result = api.getItemCount(mmsid, holid)
    if result and result.errs:
        raise Exception(*result.errs)

    print('Number of items:', itemcount)


def test_update_item(mmsid, holid, itemid):
    result = api.getItem(mmsid, holid, itemid)
    xml = result.data
    errs = result.errs
    if errs:
        raise Exception(*errs)

    item = Item.fromXml(xml)
    lookup = { ItemData.ROOT_TAG+'__internal_note_3': 'whatever'}
    xml = item.setTagValues(xml, lookup)
    xml,errs = api.updateItem(mmsid, holid, itemid, xml)

    print('item updated: {}'.format(itemid))

def test_delete_item(mmsid, holid, itemid):
    result = api.deleteItem(mmsid, holid, itemid)
    xml = result.data
    errs = result.errs
    if errs:
        raise Exception(*errs)

    print("item deleted {}".format(itemid))

def test_resolve_barcode(barcode):
    (xml, errs, item_not_found, mmsid, holid, itemid) = api.resolveBarcode(barcode)
    if item_not_found:
        print("item not found")
    if errs and not item_not_found:
        raise Exception(*errs)
    if not item_not_found:
        print(f"barcode resolved: mmsid {mmsid}, holid {holid},itemid {itemid}")

def test_create_item(mmsid, holid):
    result = api.createItem(mmsid, holid)
    xml = result.data
    errs = result.errs
    if errs:
        raise Exception(*errs)

    item = Item.fromXml(xml)
    itemid = item.item_data.item_id

    lookup = { ItemData.ROOT_TAG+'__internal_note_3': 'whatever 2'}
    xml = item.setTagValues(xml, lookup)
    result = api.updateItem(mmsid, holid, itemid, xml)
    xml = result.data
    errs = result.errs
    if errs:
        raise Exception(*errs)

    print('item created (and updated): {}'.format(itemid))
 

def test_create_set(urlparams):
    setid,result = api.createSet(**urlparams)


#def test_create_set(setname,urlparams):

#    setid,result = api.createItemizedBibRecordSet(setname)
#    xml = result.data
#    errs = result.errs
#    if errs:
#        raise Exception (*errs)
#    
#    print('set created id: {}'.format(setid))

def test_get_set(setid):
    result = api.getSet(setid)
    xml = result.data
    errs = result.errs
    if errs:
        raise Exception(*errs)

    print(xml)

def test_delete_set(setid):
    result = api.deleteSet(setid)
    xml = result.data
    errs = result.errs
    if errs:
        raise Exception (*errs)

    print('set deleted, seitd: {}'.format(setid))

def test_find_set_by_name(setname):
    setid,result = api.findSetByName(setname)
    if result and result.errs:
        raise Exception (*result.errs)
    
    if setid:
        print('set found, setid: {}'.format(setid))
    else:
        print('no set found')

def test_fetch_set_members(setid,offset,limit,max_records):
    members,result = api.fetchSetMembers(setid,offset=offset,limit=limit,max_records=max_records)
    if result and result.errs:
        raise Exception (*result.errs)

    for member in members:
        print(member)

def test_fetch_set_members_mt(setid,offset,limit,max_records):
    members,result = api.fetchSetMembers(setid,offset=offset,limit=limit,max_records=max_records)
    if result and result.errs:
        raise Exception (*result.errs)

    queue = []
    results = {}
    items = []
    
    while len(members)>0:
        member = members.pop()

        # get results from finished threds
        done = [x for x in queue if not x.is_alive()]        
        for x in done:
            print("thread done",x.name )
            results[x.name] = x.result

        # max 20 active thread running
        queue = [x for x in queue if x.is_alive()]        
        print(len(queue))
        if len(queue)>=20:
            time.sleep(1)
        else:
            x = APIThread(target=api.sendAPIRequest,args=(member.link,)) 
            queue.append(x)
            x.start()
            print("thread started",x.name )

    # wait for remaining threads:
    for x in queue:
        print("waiting for",x.name )
        x.join()

    #get results from remaining threads
    done = [x for x in queue if not x.is_alive()]        
    for x in done:
        print("thread done",x.name )
        results[x.name] = x.result

    for k,v in results.items():
        result = v
        if result.errs:
            print(k,result.errs)
        else:
            item = Item.fromXml(result.data)
            items.append(item)
            print(k,item.item_data.barcode)

    print('tem count',len(items))


def test_get_user(userid,urlparams):
    result = api.getUser(userid,**urlparams)
    xml = result.data
    errs = result.errs
    if errs:
        raise Exception(*errs)

    print(xml)

def test_delete_user(userid,urlparams):
    result = api.deleteUser(userid,**urlparams)
    xml = result.data
    errs = result.errs
    if errs:
        raise Exception(*errs)

    print(xml)

def test_update_user_tag_values(userid, vals):
    result = api.getUser(userid)
    xml = result.data
    errs = result.errs
    if errs:
        raise Exception(*errs)

    xml = User.setTagValues(xml, vals)
    result = api.updateUser(userid, xml)
    xml = result.data
    errs = result.errs
    if errs:
        raise Exception(*errs)

    print(xml)

def test_get_user_loans(userid,urlparams):
    result = api.getUserLoans(userid,**urlparams)
    xml = result.data
    errs = result.errs
    if errs:
        raise Exception(*errs)

    print(xml)
    loans = Loan.multiFromXml(xml)
    for x in loans:
        print(x)

def test_get_user_fees(userid,urlparams):
    result = api.getUserFees(userid,**urlparams)
    xml = result.data
    errs = result.errs
    if errs:
        raise Exception(*errs)

    print(xml)
    fees = Fee.multiFromXml(xml)
    for x in fees:
        print(x)

def test_pay_user_fee(userid,feeid,urlparams):
    result = api.payUserFee(userid,feeid,**urlparams)
    xml = result.data
    errs = result.errs
    if errs:
        raise Exception(*errs)

    print(xml)

def test_waive_user_fee(userid,feeid,urlparams):
    result = api.payUserFee(userid,feeid,op='waive',**urlparams)
    xml = result.data
    errs = result.errs
    if errs:
        raise Exception(*errs)

    print(xml)

def test_op_user_fee(userid,feeid,urlparams):
    result = api.payUserFee(userid,feeid,**urlparams)
    xml = result.data
    errs = result.errs
    if errs:
        raise Exception(*errs)

    print(xml)

def test_list_requests(mmsid, holid, itemid):
    result = api.listRequests(mmsid, holid, itemid)
    xml = result.data
    errs = result.errs
    if errs:
        raise Exception(*errs)

    objs = Request.multiFromXml(xml,dont_mind_unknown_tags=False)
    for o in objs:
        print(o)
        print(o.xml)

def test_get_request(mmsid, holid, itemid, requestid):
    result = api.getRequest(mmsid, holid, itemid, requestid)
    xml = result.data
    errs = result.errs
    if errs:
        raise Exception(*errs)

    print(xml)

def test_delete_request(mmsid, holid, itemid, requestid):
    result = api.deleteRequest(mmsid, holid, itemid, requestid)
    xml = result.data
    errs = result.errs
    if errs:
        raise Exception(*errs)

    print(xml)

def test_update_item_tag_values(mmsid, holid, itemid, vals):
    result = api.getItem(mmsid, holid, itemid)
    xml = result.data
    errs = result.errs
    if errs:
        raise Exception(*errs)

    xml = Item.setTagValues(xml, vals)
    result = api.updateItem(mmsid, holid, itemid, xml)
    xml = result.data
    errs = result.errs
    if errs:
        raise Exception(*errs)

    print(xml)

def test_change_items_job(setid, vals):
    result = api.runChangeItemsJob(setid, **vals)
    xml = result.data
    errs = result.errs
    if errs:
        raise Exception(*errs)

    print(xml)

def test_get(url):
    result = api.sendAPIRequest(url,type='GET',xml=None,json=None)
    xml = result.data
    errs = result.errs
    if errs:
        raise Exception(*errs)

    print(prettyPrint(xml))

def test_create_user():
    xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<user>
  <record_type>PUBLIC</record_type>
  <account_type>EXTERNAL</account_type>
  <external_id>TISS</external_id>
  <status>ACTIVE</status>
  <primary_id>TISS4711</primary_id>
  <job_category>Borrower</job_category>
  <campus_code>TU</campus_code>
  <first_name>Marina</first_name>
  <last_name>MUSTERFRAUR</last_name>
  <preferred_language>de</preferred_language>
  <expiry_date>2022-10-11Z</expiry_date>
  <purge_date>2022-10-11Z</purge_date>
  <birth_date>1955-07-26Z</birth_date>
  <user_group>11</user_group>
  <user_identifiers>
    <user_identifier segment_type="External">
      <id_type>01</id_type>
      <value>7084396406</value>
      <status>ACTIVE</status>
    </user_identifier>
  </user_identifiers>
  <contact_info>
    <addresses>
      <address segment_type="External">
        <line1>Marina MUSTERFRAU</line1>
        <line2>Holweg 25</line2>
        <line3>9999 Fugging</line3>
        <address_types>
          <address_type>home</address_type>
        </address_types>
      </address>
      <address preferred="true" segment_type="External">
        <line1>Marina MUSTERFRAU</line1>
        <line2>Holzweg 245/line2>
        <line3>4811 Wien-Land</line3>
        <address_types>
          <address_type>work</address_type>
        </address_types>
      </address>
    </addresses>
    <emails>
      <email preferred="true" segment_type="External">
        <email_address>marina.musterfrau@nowhere.com</email_address>
        <email_types>
          <email_type>personal</email_type>
        </email_types>
      </email>
    </emails>
    <phones>
      <phone preferred="true" segment_type="External">
        <phone_number>+43 123 1234567890</phone_number>
        <phone_types>
          <phone_type>home</phone_type>
        </phone_types>
      </phone>
    </phones>
  </contact_info>
  <user_statistics>
    <user_statistic segment_type="External">
      <category_type>Faculty</category_type>
      <statistic_category>F50</statistic_category>
    </user_statistic>
    <user_statistic segment_type="External">
      <category_type>Usertype</category_type>
      <statistic_category>U11</statistic_category>
    </user_statistic>
  </user_statistics>
</user>
    '''
    result = api.createUser(xml)
    xml = result.data
    errs = result.errs
    if errs:
        raise Exception(*errs)

    print(prettyPrint(xml))

def test_marc_to_dc():
    xml = """<record xmlns="http://www.loc.gov/MARC21/slim"
                    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.loc.gov/MARC21/slim http://www.loc.gov/standards/marcxml/schema/MARC21slim.xsd">
                    <leader>02476nam a2200745 c 4500</leader>
                    <controlfield tag="001">997828835803336</controlfield>
                    <controlfield tag="005">20211115110553.0</controlfield>
                    <controlfield tag="007">cr||||||||||||</controlfield>
                    <controlfield tag="008">211106s2022    ||||||||o|||| 00||||ger</controlfield>
                    <controlfield tag="009">AC16378159</controlfield>
                    <datafield tag="015" ind1=" " ind2=" ">
                        <subfield code="a">21,O12</subfield>
                        <subfield code="2">dnb</subfield>
                    </datafield>
                    <datafield tag="016" ind1="7" ind2=" ">
                        <subfield code="a">1245212273</subfield>
                        <subfield code="2">DE-101</subfield>
                    </datafield>
                    <datafield tag="020" ind1=" " ind2=" ">
                        <subfield code="a">9783662636350</subfield>
                    </datafield>
                    <datafield tag="024" ind1="7" ind2=" ">
                        <subfield code="a">10.1007/978-3-662-63635-0</subfield>
                        <subfield code="2">doi</subfield>
                    </datafield>
                    <datafield tag="035" ind1=" " ind2=" ">
                        <subfield code="a">(AT-OBV)AC16378159</subfield>
                    </datafield>
                    <datafield tag="035" ind1=" " ind2=" ">
                        <subfield code="a">(DE-599)DNB1245212273</subfield>
                    </datafield>
                    <datafield tag="035" ind1=" " ind2=" ">
                        <subfield code="a">(DE-101)1245212273</subfield>
                    </datafield>
                    <datafield tag="035" ind1=" " ind2=" ">
                        <subfield code="a">(EXLNZ-43ACC_NETWORK)99146402177503331</subfield>
                    </datafield>
                    <datafield tag="040" ind1=" " ind2=" ">
                        <subfield code="a">AT-UBTUW</subfield>
                        <subfield code="b">ger</subfield>
                        <subfield code="c">DE-101</subfield>
                        <subfield code="d">AT-FHS</subfield>
                        <subfield code="e">rda</subfield>
                    </datafield>
                    <datafield tag="041" ind1=" " ind2=" ">
                        <subfield code="a">ger</subfield>
                    </datafield>
                    <datafield tag="044" ind1=" " ind2=" ">
                        <subfield code="c">XA-DE-BE</subfield>
                    </datafield>
                    <datafield tag="084" ind1=" " ind2=" ">
                        <subfield code="a">340</subfield>
                        <subfield code="q">DE-101</subfield>
                        <subfield code="2">sdnb</subfield>
                    </datafield>
                    <datafield tag="245" ind1="0" ind2="0">
                        <subfield code="a">Mobilitäts- und Transportrecht in Europa</subfield>
                        <subfield code="b">Bestandsaufnahme und Zukunftsperspektiven</subfield>
                    </datafield>
                    <datafield tag="250" ind1=" " ind2=" ">
                        <subfield code="a">1. Auflage 2022</subfield>
                    </datafield>
                    <datafield tag="264" ind1=" " ind2="1">
                        <subfield code="a">Berlin, Heidelberg</subfield>
                        <subfield code="b">Springer Berlin Heidelberg</subfield>
                        <subfield code="c">2022</subfield>
                    </datafield>
                    <datafield tag="300" ind1=" " ind2=" ">
                        <subfield code="a">1 Online-Ressource (293 Seiten)</subfield>
                    </datafield>
                    <datafield tag="336" ind1=" " ind2=" ">
                        <subfield code="b">txt</subfield>
                    </datafield>
                    <datafield tag="337" ind1=" " ind2=" ">
                        <subfield code="b">c</subfield>
                    </datafield>
                    <datafield tag="338" ind1=" " ind2=" ">
                        <subfield code="b">cr</subfield>
                    </datafield>
                    <datafield tag="347" ind1=" " ind2=" ">
                        <subfield code="a">Textdatei</subfield>
                        <subfield code="b">PDF</subfield>
                    </datafield>
                    <datafield tag="490" ind1="0" ind2=" ">
                        <subfield code="a">Bibliothek des Wirtschaftsrechts</subfield>
                    </datafield>
                    <datafield tag="506" ind1="0" ind2=" ">
                        <subfield code="f">Unrestricted online access</subfield>
                        <subfield code="2">star</subfield>
                    </datafield>
                    <datafield tag="540" ind1=" " ind2=" ">
                        <subfield code="f">CC-BY-4.0</subfield>
                        <subfield code="2">cc</subfield>
                        <subfield code="u">https://creativecommons.org/licenses/by/4.0/deed.de</subfield>
                    </datafield>
                    <datafield tag="650" ind1=" " ind2="7">
                        <subfield code="a">Transportrecht</subfield>
                        <subfield code="0">(DE-588)4225140-0</subfield>
                        <subfield code="2">gnd</subfield>
                    </datafield>
                    <datafield tag="650" ind1=" " ind2="7">
                        <subfield code="a">Verkehrspolitik</subfield>
                        <subfield code="0">(DE-588)4062955-7</subfield>
                        <subfield code="2">gnd</subfield>
                    </datafield>
                    <datafield tag="650" ind1=" " ind2="7">
                        <subfield code="a">Binnenmarkt</subfield>
                        <subfield code="0">(DE-588)4145576-9</subfield>
                        <subfield code="2">gnd</subfield>
                    </datafield>
                    <datafield tag="650" ind1=" " ind2="7">
                        <subfield code="a">Verkehrsrecht</subfield>
                        <subfield code="0">(DE-588)4187827-9</subfield>
                        <subfield code="2">gnd</subfield>
                    </datafield>
                    <datafield tag="650" ind1=" " ind2="7">
                        <subfield code="a">Verkehr</subfield>
                        <subfield code="0">(DE-588)4062901-6</subfield>
                        <subfield code="2">gnd</subfield>
                    </datafield>
                    <datafield tag="651" ind1=" " ind2="7">
                        <subfield code="a">Europa</subfield>
                        <subfield code="0">(DE-588)4015701-5</subfield>
                        <subfield code="2">gnd</subfield>
                    </datafield>
                    <datafield tag="653" ind1=" " ind2=" ">
                        <subfield code="a">Eisenbahnverkehr</subfield>
                    </datafield>
                    <datafield tag="653" ind1=" " ind2=" ">
                        <subfield code="a">Gerichtszuständigkeit</subfield>
                    </datafield>
                    <datafield tag="653" ind1=" " ind2=" ">
                        <subfield code="a">Transportrecht</subfield>
                    </datafield>
                    <datafield tag="653" ind1=" " ind2=" ">
                        <subfield code="a">UN-Kaufrecht</subfield>
                    </datafield>
                    <datafield tag="653" ind1=" " ind2=" ">
                        <subfield code="a">Umweltrecht</subfield>
                    </datafield>
                    <datafield tag="653" ind1=" " ind2=" ">
                        <subfield code="a">EU-Recht</subfield>
                    </datafield>
                    <datafield tag="653" ind1=" " ind2=" ">
                        <subfield code="a">Güterverkehr</subfield>
                    </datafield>
                    <datafield tag="653" ind1=" " ind2=" ">
                        <subfield code="a">Automatisiertes Fahren</subfield>
                    </datafield>
                    <datafield tag="653" ind1=" " ind2=" ">
                        <subfield code="a">COTIF</subfield>
                    </datafield>
                    <datafield tag="653" ind1=" " ind2=" ">
                        <subfield code="a">Mobilität</subfield>
                    </datafield>
                    <datafield tag="653" ind1=" " ind2=" ">
                        <subfield code="a">Internationales Privat- und Prozessrecht</subfield>
                    </datafield>
                    <datafield tag="653" ind1=" " ind2=" ">
                        <subfield code="a">Vertragsrecht</subfield>
                    </datafield>
                    <datafield tag="653" ind1=" " ind2=" ">
                        <subfield code="a">Verkehrs- und Haftungsrecht</subfield>
                    </datafield>
                    <datafield tag="653" ind1=" " ind2=" ">
                        <subfield code="a">Open Access</subfield>
                    </datafield>
                    <datafield tag="653" ind1=" " ind2=" ">
                        <subfield code="a">Personenverkehr</subfield>
                    </datafield>
                    <datafield tag="653" ind1=" " ind2=" ">
                        <subfield code="a">Verkehrswirtschaft</subfield>
                    </datafield>
                    <datafield tag="653" ind1=" " ind2=" ">
                        <subfield code="a">Verkehrspolitik</subfield>
                    </datafield>
                    <datafield tag="653" ind1=" " ind2=" ">
                        <subfield code="a">Europäischer Binnenmarkt</subfield>
                    </datafield>
                    <datafield tag="653" ind1=" " ind2=" ">
                        <subfield code="a">European Economic Law</subfield>
                    </datafield>
                    <datafield tag="653" ind1=" " ind2=" ">
                        <subfield code="a">Private International Law, International &amp; Foreign Law, Comparative Law</subfield>
                    </datafield>
                    <datafield tag="700" ind1="1" ind2=" ">
                        <subfield code="a">Laimer, Simon</subfield>
                        <subfield code="d">1975-</subfield>
                        <subfield code="0">(DE-588)132496062</subfield>
                        <subfield code="4">edt</subfield>
                    </datafield>
                    <datafield tag="710" ind1="2" ind2=" ">
                        <subfield code="a">Springer-Verlag GmbH</subfield>
                        <subfield code="0">(DE-588)1065168780</subfield>
                        <subfield code="4">pbl</subfield>
                    </datafield>
                    <datafield tag="776" ind1="0" ind2="8">
                        <subfield code="i">Erscheint auch als</subfield>
                        <subfield code="n">Druck-Ausgabe</subfield>
                        <subfield code="z">9783662636343</subfield>
                    </datafield>
                    <datafield tag="856" ind1="4" ind2="0">
                        <subfield code="u">https://doi.org/10.1007/978-3-662-63635-0</subfield>
                        <subfield code="x">Resolving-System</subfield>
                        <subfield code="3">Volltext</subfield>
                    </datafield>
                    <datafield tag="912" ind1=" " ind2=" ">
                        <subfield code="a">ZDB-2-SZR</subfield>
                    </datafield>
                    <datafield tag="912" ind1=" " ind2=" ">
                        <subfield code="a">ZDB-2-SOB</subfield>
                    </datafield>
                    <datafield tag="970" ind1="4" ind2=" ">
                        <subfield code="b">DE-101</subfield>
                    </datafield>
                    <datafield tag="983" ind1=" " ind2=" ">
                        <subfield code="a">BAU:125 AAB</subfield>
                        <subfield code="d">Straßenrecht und Verkehrsrecht, Transportrecht</subfield>
                        <subfield code="g">Europa</subfield>
                        <subfield code="9">local</subfield>
                    </datafield>
                    <datafield tag="983" ind1=" " ind2=" ">
                        <subfield code="a">BAU:858 AAB</subfield>
                        <subfield code="d">Güterverkehr, Gütertransport</subfield>
                        <subfield code="g">Europa</subfield>
                        <subfield code="9">local</subfield>
                    </datafield>
                    <datafield tag="983" ind1=" " ind2=" ">
                        <subfield code="a">BAU: JUR:</subfield>
                        <subfield code="9">local</subfield>
                    </datafield>
                    <datafield tag="983" ind1=" " ind2=" ">
                        <subfield code="a">AT-OBV</subfield>
                        <subfield code="z">202111</subfield>
                        <subfield code="5">TUWSUC</subfield>
                        <subfield code="9">local</subfield>
                    </datafield>
                </record>"""
    mr = MarcRecord()
    mr.parse(xml)
    print(mr.toBibXML())
    dc = mr.toDublinCore()
    print(dc.toXML())

def test_rdf_get_work(mmsid):
    result = api.getRDFWork(mmsid)
    xml = result.data
    errs = result.errs
    if errs:
        raise Exception(*errs)

    print(xml)

def test_rdf_get_manifestation(mmsid):
    result = api.getRDFManifestation(mmsid)
    xml = result.data
    errs = result.errs
    if errs:
        raise Exception(*errs)

    print(xml)

def test_extend_set_by(setid=None,setname=None,setid_extend_by=None,setname_extend_by=None):
    members, result = api.extendSet(setid=setid,setname=setname,setid_extend_by=setid_extend_by,setname_extend_by=setname_extend_by)
    if result and result.errs:
        raise Exception(*result.errs)

    print(members)

def test_set_add_mmsid(setid=None,setname=None,mmsid=None):
    if not setid:
        setid,result = api.findSetByName(setname)
        if result and result.errs:    
            raise Exception (*result.errs)
        
        if setid:
            print('set found, setid: {}'.format(setid))
        else:
            print('no set found')
            exit(1)

    result = api.addIdToSet(setid,mmsid)
    xml = result.data
    errs = result.errs
    if errs:
        raise Exception(*errs)

    print(xml)
        

def test_get_letters():
    result = api.getLetters()
    xml = result.data
    errs = result.errs
    if errs:
        raise Exception(*errs)

    letters = Letter.multiFromXml(xml)
    print(dir(letters[0]))
    print(letters[0].attribs_table)

def test_get_analytics_paths():
    result = api.getAnalyticsPaths()
    xml = result.data
    errs = result.errs
    if errs:
        raise Exception(*errs)
    
    print(xml)

def test_get_analytics_report(urlparams):
#    filter = api.makeAnalyticsFilter(operator='equal',
#                                     column='"Fulfillment"."Item Location at time of loan"."Location Code"',
#                                     value='8O3')
    
    filter = '''<?xml version="1.0"?>
<sawx:expr xmlns:saw="com.siebel.analytics.web/report/v1.1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:sawx="com.siebel.analytics.web/expression/v1.1" xsi:type="sawx:logical" op="and" xmlVersion="201201160">
	<sawx:expr xmlns:saw="com.siebel.analytics.web/report/v1.1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:sawx="com.siebel.analytics.web/expression/v1.1" xsi:type="sawx:comparison" op="equal" xmlVersion="201201160">
		<sawx:expr xsi:type="sawx:sqlExpression">"Fund Ledger"."Fund Ledger Status"</sawx:expr>
		<sawx:expr xsi:type="xsd:string">ACTIVE</sawx:expr>
	</sawx:expr>
	<sawx:expr xmlns:saw="com.siebel.analytics.web/report/v1.1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:sawx="com.siebel.analytics.web/expression/v1.1" xsi:type="sawx:comparison" op="equal" xmlVersion="201201160">
		<sawx:expr xsi:type="sawx:sqlExpression">"Physical Item Details"."Lifecyle"</sawx:expr>
		<sawx:expr xsi:type="xsd:string">Active</sawx:expr>
	</sawx:expr>
	<sawx:expr xmlns:saw="com.siebel.analytics.web/report/v1.1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:sawx="com.siebel.analytics.web/expression/v1.1" xsi:type="sawx:comparison" op="equal" xmlVersion="201201160">
		<sawx:expr xsi:type="sawx:sqlExpression">"Fiscal Period"."Fiscal Period Status"</sawx:expr>
		<sawx:expr xsi:type="xsd:string">ACTIVE</sawx:expr>
	</sawx:expr>
'''
    filter += '<sawx:expr xmlns:saw="com.siebel.analytics.web/report/v1.1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:sawx="com.siebel.analytics.web/expression/v1.1" xsi:type="sawx:list" op="in" xmlVersion="201201160">'
    filter += '<sawx:expr xsi:type="sawx:sqlExpression">"Fund Ledger"."Fund Ledger Code"</sawx:expr>'
    filter += '<sawx:expr xsi:type="xsd:string">'
    filter += '3600'
    filter += '</sawx:expr>'
    filter += '</sawx:expr>'
    filter += '</sawx:expr>'

    urlparams['filter'] = filter
    xml, result = api.getAnalyticsReport(**urlparams)
    if result and result.errs:
        raise Exception(*result.errs)

    print(xml)


def test_hardcoded():
#    xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
#    <set link="https://api-eu.hosted.exlibrisgroup.com/almaws/v1/conf/sets/9423665400003336">
#        <name>8O5</name>
#        <query>IEP where HOLDING ((permanentPhysicalLocation OUTER_EQUAL ((EHB : 8O5))))</query>
#    </set>    
#    """
#    setid,result = api.createSet(name='8O5',
#                           type='LOGICAL',
#                           content='IEP',
#                           private='false',
#                           query='IEP where HOLDING ((permanentPhysicalLocation OUTER_EQUAL ((EHB : 8O4))))')
#                           
#    if result and result.errs:
#        raise Exception(*result.errs)
#
#    print(setid)
#    print(result.data)


#    xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
#    <set>
#        <name>COLLL</name>
#        <query>BIB_MMS where BIB_MMS ((local_field_983 CONTAIN "TUWWAL") AND BIB_MMS (local_field_983 CONTAIN "202304"))</query>
#    </set>    
#    """
#
#    setid = 9423589390003336 
#    result = api.updateSet(setid,xml)
#    if result and result.errs:
#        raise Exception(*result.errs)
#
#    print(result.data)

    pass

def test_get_portfolios():
    mmsid = OPTIONS[OP_MMSID]
    result = api.getPortfolios(mmsid)
    xml = result.data
    errs = result.errs
    if errs:
        raise Exception(*errs)

    portfolios, result = api.getPortfoliosAsObjects(mmsid)
    if result and result.errs:
        raise Exception(*result.errs)

    print('number of portfolios:', len(portfolios))
    for portfolio in portfolios:
        print(portfolio.id)
        print(portfolio.resource_metadata)

def test_get_portfolio():
    mmsid = OPTIONS[OP_MMSID]
    portfolioid = OPTIONS[OP_PORTFOLIOID]

    result = api.getPortfolio(mmsid,portfolioid)
    xml = result.data
    errs = result.errs
    if errs:
        raise Exception(*errs)

    print(xml)

def test_delete_portfolio():
    mmsid = OPTIONS[OP_MMSID]
    portfolioid = OPTIONS[OP_PORTFOLIOID]

    result = api.deletePortfolio(mmsid,portfolioid)
    xml = result.data
    errs = result.errs
    if errs:
        raise Exception(*errs)

    print(xml)

def test_create_portfolio():
    collectionid = OPTIONS.get(OP_COLLECTIONID,None)
    serviceid = OPTIONS.get(OP_SERVICEID,None)
    mmsid = OPTIONS.get(OP_MMSID,None)
    url = OPTIONS.get(OP_URL,None)

    result = api.createPortfolio(collectionid=collectionid,serviceid=serviceid,mmsid=mmsid,link=url)
    if result and result.errs:
        raise Exception(*result.errs)
    print(result.data)

    # mmsid=998089144303336

    # 'http://arw.zzz:8000/article/id/715/'


def test_sru():
    params = OPTIONS[OP_URLPARAMS]
    result = api.sendSRURequest(**params)
    if result and result.errs:
        raise Exception(*result.errs)
    print(result.data)

    xml = result.data
    xml = stripXmlDeclaration(xml)
    records = MarcRecord.parseMultiple(xml)
    for mr in records:
        print (mr)

def test_get_requested_resources():
    library = OPTIONS[OP_LIBRARY] 
    circ_desk = OPTIONS[OP_CIRCDESK] 
    params = OPTIONS.get(OP_URLPARAMS,{})
    result = api.getRequestedResources(library,circ_desk,**params)
    if result and result.errs:
        raise Exception(*result.errs)
    print(result.data)

    soup = BeautifulSoup(result.data, "xml")
    l = soup.find_all('requested_resource')
    for i,x in enumerate(l,1):
        print(i,x.resource_metadata)
        print(i,x.requests)

parser = argparse.ArgumentParser()
setParserArguments(parser,TESTS,API_TARGETS)
argcomplete.autocomplete(parser)
test, api_target = getParserValues(parser)

logger,warn_log = setupLogging(os.path.basename(__file__),test,OPTIONS[OP_DIRLOG])
logger.info(f'test = {test}')
logger.info(f'api_target = {api_target}')
for k,v in OPTIONS.items():
    logger.info(f'{k}: {v}')
if warn_log:
    logger.warning(warn_log)

try:
    api=API(file_cfg=OPTIONS[OP_APICFG])
    api.setAPITarget(api_target)
    api.setUseDatabaseLogging(OPTIONS[OP_DBLOG],OPTIONS[OP_DBLOGLABEL])
    api.setLogLevel(OPTIONS[OP_LOGLEVEL])
except Exception as e:
    print(traceback.format_exc())
    exit(1)

try:
    if (test != TEST_RESOLVE_BARCODE 
        and OPTIONS[OP_BARCODE] 
        and not OPTIONS[OP_MMSID] 
        and not OPTIONS[OP_HOLID] 
        and not OPTIONS[OP_ITEMID]):
        (item_not_found, mmsid, holid, itemid, result) = api.resolveBarcode(OPTIONS[OP_BARCODE])
        if result.errs:
            raise Exception(*result.errs)
        OPTIONS[OP_MMSID] = mmsid
        OPTIONS[OP_HOLID] = holid
        OPTIONS[OP_ITEMID] = itemid

    if test == TEST_GET:
        if not OPTIONS[OP_URL]:
            print("url required")
            exit(1)
        test_get(OPTIONS[OP_URL])

    if test == TEST_CREATE_BIB:
        test_create_bib()
    elif test == TEST_GET_BIB:
        if not OPTIONS[OP_MMSID]:
            print("mmsidrequired")
            exit(1)
        test_get_bib(OPTIONS[OP_MMSID])
    elif test == TEST_UPDATE_BIB:
        if not OPTIONS[OP_MMSID]:
            print("mmsidrequired")
            exit(1)
        test_update_bib(OPTIONS[OP_MMSID])
    elif test == TEST_CREATE_SET:
        if not OPTIONS[OP_URLPARAMS]:
            print("urlparams required")
            exit(1)
        test_create_set(OPTIONS[OP_URLPARAMS])

#        if not OPTIONS[OP_SETNAME]:
#            print("setname required")
#            exit(1)
#        test_create_set(OPTIONS[OP_SETNAME])
    elif test == TEST_DELETE_SET:
        if not OPTIONS[OP_SETID]:
            print("setid required")
            exit(1)
        test_delete_set(OPTIONS[OP_SETID])
    elif test == TEST_GET_SET:
        if not OPTIONS[OP_SETID]:
            print("setid required")
            exit(1)
        test_get_set(OPTIONS[OP_SETID])
    elif test == TEST_FIND_SET_BY_NAME:
        if not OPTIONS[OP_SETNAME]:
            print("setname required")
            exit(1)
        test_find_set_by_name(OPTIONS[OP_SETNAME])
    elif test == TEST_SET_MEMBERS:
        if not OPTIONS[OP_SETID]:
            print("setid required")
            exit(1)
        test_fetch_set_members(OPTIONS[OP_SETID],offset=OPTIONS[OP_OFFSET],limit=OPTIONS[OP_LIMIT],max_records=OPTIONS[OP_MAXRECORDS])
    elif test == TEST_SET_MEMBERS_MT:
        if not OPTIONS[OP_SETID]:
            print("setid required")
            exit(1)
        test_fetch_set_members_mt(OPTIONS[OP_SETID],offset=OPTIONS[OP_OFFSET],limit=OPTIONS[OP_LIMIT],max_records=OPTIONS[OP_MAXRECORDS])
    elif test == TEST_GET_HOLDING:
        if not OPTIONS[OP_MMSID] or not OPTIONS[OP_HOLID]:
            print("mmsid,holid required")
            exit(1)
        test_get_holding(OPTIONS[OP_MMSID],OPTIONS[OP_HOLID])
    elif test == TEST_CREATE_HOLDING:
        if not OPTIONS[OP_MMSID]:
            print("mmsid required")
            exit(1)
        test_create_holding(OPTIONS[OP_MMSID])
    elif test == TEST_SUPPRESS_HOLDING:
        if not OPTIONS[OP_MMSID] or not OPTIONS[OP_HOLID] or not OPTIONS[OP_FLAGS]:
            print("mmsid,holid,flags required")
            exit(1)
        test_suppress_holding(OPTIONS[OP_MMSID],OPTIONS[OP_HOLID],OPTIONS[OP_FLAGS])
    elif test == TEST_CREATE_ITEM:
        if not OPTIONS[OP_MMSID] or not OPTIONS[OP_HOLID]:
            print("mmsid,holid required")
            exit(1)
        test_create_item(OPTIONS[OP_MMSID],OPTIONS[OP_HOLID])
    elif test == TEST_GET_ITEM:
        if not OPTIONS[OP_MMSID] or not OPTIONS[OP_HOLID] or not OPTIONS[OP_ITEMID]:
            print("mmsid,holid,itemid required")
            exit(1)
        test_get_item(OPTIONS[OP_MMSID],OPTIONS[OP_HOLID],OPTIONS[OP_ITEMID])
    elif test == TEST_GET_ITEM_VIA_BARCODE:
        if not OPTIONS[OP_BARCODE]:
            print("barcode")
            exit(1)
        test_get_item_via_barcode(OPTIONS[OP_BARCODE])
    elif test == TEST_GET_ITEMCOUNT:
        if not OPTIONS[OP_MMSID] or not OPTIONS[OP_HOLID]:
            print("mmsid,holid required")
            exit(1)
        test_get_itemcount(OPTIONS[OP_MMSID],OPTIONS[OP_HOLID])
    elif test == TEST_UPDATE_ITEM:
        if not OPTIONS[OP_MMSID] or not OPTIONS[OP_HOLID] or not OPTIONS[OP_ITEMID]:
            print("mmsid,holid,itemid required")
            exit(1)
        test_update_item(OPTIONS[OP_MMSID],OPTIONS[OP_HOLID],OPTIONS[OP_ITEMID])
    elif test == TEST_DELETE_ITEM:
        if not OPTIONS[OP_MMSID] or not OPTIONS[OP_HOLID] or not OPTIONS[OP_ITEMID]:
            print("mmsid,holid,itemid required")
            exit(1)
        test_delete_item(OPTIONS[OP_MMSID],OPTIONS[OP_HOLID],OPTIONS[OP_ITEMID])
    elif test == TEST_UPDATE_ITEM_TAG_VALUES:
        if not OPTIONS[OP_MMSID] or not OPTIONS[OP_HOLID] or not OPTIONS[OP_ITEMID] or not OPTIONS[OP_URLPARAMS]:
            print("mmsid,holid,itemid,urlparams required")
            exit(1)
        test_update_item_tag_values(OPTIONS[OP_MMSID],OPTIONS[OP_HOLID],OPTIONS[OP_ITEMID],OPTIONS[OP_URLPARAMS])
    elif test == TEST_CHANGE_ITEMS_JOB:
        if not OPTIONS[OP_SETID] or not OPTIONS[OP_URLPARAMS]:
            print("setid,urlparams required")
            exit(1)
        test_change_items_job(OPTIONS[OP_SETID],OPTIONS[OP_URLPARAMS])
    elif test == TEST_RESOLVE_BARCODE:
        if not OPTIONS[OP_BARCODE]:
            print("barcode required")
            exit(1)
        test_resolve_barcode(OPTIONS[OP_BARCODE])
    elif test == TEST_GET_USER:
        if not OPTIONS[OP_USERID]:
            print("userid required")
            exit(1)
        urlparams = OPTIONS[OP_URLPARAMS] if OP_URLPARAMS in OPTIONS else {}
        test_get_user(OPTIONS[OP_USERID],urlparams)
    elif test == TEST_DELETE_USER:
        if not OPTIONS[OP_USERID]:
            print("userid required")
            exit(1)
        test_delete_user(OPTIONS[OP_USERID],OPTIONS[OP_URLPARAMS])
    elif test == TEST_UPDATE_USER_TAG_VALUES:
        if not OPTIONS[OP_USERID] or not OPTIONS[OP_URLPARAMS]:
            print("userid,urlparams required")
            exit(1)
        test_update_user_tag_values(OPTIONS[OP_USERID],OPTIONS[OP_URLPARAMS])
    elif test == TEST_GET_USER_FEES:
        if not OPTIONS[OP_USERID]:
            print("userid required")
            exit(1)
        test_get_user_fees(OPTIONS[OP_USERID],OPTIONS.get(OP_URLPARAMS,{}))
    elif test == TEST_GET_USER_LOANS:
        if not OPTIONS[OP_USERID]:
            print("userid required")
            exit(1)
        test_get_user_loans(OPTIONS[OP_USERID],OPTIONS[OP_URLPARAMS])
    elif test in [TEST_PAY_USER_FEE, TEST_WAIVE_USER_FEE, TEST_OP_USER_FEE]:
        if not OPTIONS[OP_USERID] or not OPTIONS[OP_FEEID]:
            print("userid,feeid required")
            exit(1)
        if test == TEST_PAY_USER_FEE:
            test_pay_user_fee(OPTIONS[OP_USERID],OPTIONS[OP_FEEID],OPTIONS[OP_URLPARAMS])
        elif test == TEST_WAIVE_USER_FEE:
            test_waive_user_fee(OPTIONS[OP_USERID],OPTIONS[OP_FEEID],OPTIONS[OP_URLPARAMS])
        elif test == TEST_OP_USER_FEE:
            test_op_user_fee(OPTIONS[OP_USERID],OPTIONS[OP_FEEID],OPTIONS[OP_URLPARAMS])

    elif test == TEST_LIST_REQUESTS:
        if not OPTIONS[OP_MMSID] or not OPTIONS[OP_HOLID] or not OPTIONS[OP_ITEMID]:
            print("mmsid, holid, itemid required")
            exit(1)
        test_list_requests(OPTIONS[OP_MMSID],OPTIONS[OP_HOLID],OPTIONS[OP_ITEMID])
    elif test == TEST_GET_REQUEST:
        if not OPTIONS[OP_MMSID] or not OPTIONS[OP_HOLID] or not OPTIONS[OP_ITEMID] or not OPTIONS[OP_REQUESTID]:
            print("mmsid, holid, itemid, requestid required")
            exit(1)
        test_get_request(OPTIONS[OP_MMSID],OPTIONS[OP_HOLID],OPTIONS[OP_ITEMID],OPTIONS[OP_REQUESTID])
    elif test == TEST_DELETE_REQUEST:
        if not OPTIONS[OP_MMSID] or not OPTIONS[OP_HOLID] or not OPTIONS[OP_ITEMID] or not OPTIONS[OP_REQUESTID]:
            print("mmsid, holid, itemid, requestid required")
            exit(1)
        test_delete_request(OPTIONS[OP_MMSID],OPTIONS[OP_HOLID],OPTIONS[OP_ITEMID],OPTIONS[OP_REQUESTID])
    elif test == TEST_CREATE_USER:
        test_create_user()
    elif test == TEST_MARC_TO_DC:
        test_marc_to_dc()
    elif test == TEST_RDF_GET_WORK:
        if not OPTIONS[OP_MMSID]:
            print("mmsidrequired")
            exit(1)
        test_rdf_get_work(OPTIONS[OP_MMSID])
    elif test == TEST_RDF_GET_MANIFESTATION:
        if not OPTIONS[OP_MMSID]:
            print("mmsidrequired")
            exit(1)
        test_rdf_get_manifestation(OPTIONS[OP_MMSID])
    elif test == TEST_SET_EXTEND:
        if not OPTIONS[OP_SETID] and not OPTIONS[OP_SETNAME]:
            print("setid or setname required")
            exit(1)
        if not OPTIONS[OP_SETID_EXTEND_BY] and not OPTIONS[OP_SETNAME_EXTEND_BY]:
            print("setid_extend_by or setname_extend_by required")
            exit(1)
        test_extend_set_by(setid=OPTIONS[OP_SETID],
            setname=OPTIONS[OP_SETNAME],
            setid_extend_by=OPTIONS[OP_SETID_EXTEND_BY],
            setname_extend_by=OPTIONS[OP_SETNAME_EXTEND_BY])
    elif test == TEST_SET_ADD_MMSID:
        if not OPTIONS[OP_SETID] and not OPTIONS[OP_SETNAME]:
            print("setid or setname required")
            exit(1)
        if not OPTIONS[OP_MMSID]:
            print("mmsid required")
            exit(1)
        test_set_add_mmsid(OPTIONS[OP_SETID],
            setname=OPTIONS[OP_SETNAME],
            mmsid=OPTIONS[OP_MMSID])

    elif test == TEST_GET_LETTERS:
        test_get_letters()
    elif test == TEST_GET_ITEMS:
        if not OPTIONS[OP_MMSID] or not OPTIONS[OP_HOLID]:
            print("mmsid and holid required")
            exit(1)
        test_get_items(OPTIONS[OP_MMSID],OPTIONS[OP_HOLID])
    elif test == TEST_GET_HOLDINGS:
        if not OPTIONS[OP_MMSID]:
            print("mmsid required")
            exit(1)
        test_get_holdings(OPTIONS[OP_MMSID])

    elif test == TEST_GET_ANALYTICS_PATHS:
        test_get_analytics_paths()

    elif test == TEST_GET_ANALYTICS_REPORT:
        if not OPTIONS[OP_URLPARAMS]:
            print("urlparams required")
            exit(1)
        test_get_analytics_report(OPTIONS[OP_URLPARAMS])


    elif test == TEST_PRINT_CONFIG:
        print(api.cfg)

    elif test == TEST_HARCODED:
        test_hardcoded()

    elif test == TEST_CREATE_PORTFOLIO:
        if not OPTIONS[OP_MMSID]:
            print("mmsid required")
            exit(1)
        if not OPTIONS[OP_URL]:
            print("url required")
            exit(1)
        if  ((OPTIONS[OP_COLLECTIONID] and not OPTIONS[OP_SERVICEID]) or
            (not OPTIONS[OP_COLLECTIONID] and OPTIONS[OP_SERVICEID])):
            print("if collectionid is given, then serviceid is required as well and vice versa")
            exit(1)

        test_create_portfolio()

    elif test == TEST_GET_PORTFOLIOS:
        if not OPTIONS[OP_MMSID]:
            print("mmsid required")
            exit(1)
        test_get_portfolios()

    elif test == TEST_GET_PORTFOLIO:
        if not OPTIONS[OP_MMSID] or not OPTIONS[OP_PORTFOLIOID]:
            print("mmsid and portfolioid required")
            exit(1)
        test_get_portfolio()

    elif test == TEST_DELETE_PORTFOLIO:
        if not OPTIONS[OP_MMSID] or not OPTIONS[OP_PORTFOLIOID]:
            print("mmsid and portfolioid required")
            exit(1)
        test_delete_portfolio()

    elif test == TEST_SRU:
        if not OPTIONS[OP_URLPARAMS]:
            print("urlparams required")
            exit(1)
        test_sru()

    elif test == TEST_GET_REQUESTED_RESOURCES:
        if not OPTIONS[OP_LIBRARY] or not OPTIONS[OP_CIRCDESK]:
            print("library and circdesk required")
            exit(1)
        test_get_requested_resources()


except Exception as e:
    print(traceback.format_exc())
    exit(1)




