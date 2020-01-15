import json
import os
import codecs
import collections
import lxml
from lxml import etree

from django.conf import settings

from core import models as core_models
from journal import models
from press import models as press_models
from utils import setting_handler
from submission import models as submission_models

from utils.alma import MarcRecord,DataField,ControlField,Leader

def toMarc(article):
    record=MarcRecord()
    article=submission_models.Article.objects.get(pk=article_id)
    #title
    datafield=DataField("245","1","0")
    datafield.addSubfield("a",article.title)
    if article.subtitle:
        datafield.addSubfield("b",article.subtitle)
    record.addDataField(datafield)

    return record.toXML()








    text="""
    <bib>
    <?xml version="1.0" encoding="UTF-8"?>
    <record>
        <leader>03012naa a2200373 c 4500</leader>
        <controlfield tag="001">997661148503336</controlfield>
        <controlfield tag="007">cr#|||||||||||</controlfield>
        <controlfield tag="008">191028|2019    |||     o     ||| 0     c</controlfield>
        <datafield tag="024" ind1="7" ind2=" ">
        <subfield code="a">urn:nbn:at:at-ubtuw:4-3370</subfield>
        <subfield code="2">urn</subfield>
        </datafield>
        <datafield tag="035" ind1=" " ind2=" ">
        <subfield code="a">(VLID)4499128</subfield>
        </datafield>
        <datafield tag="040" ind1=" " ind2=" ">
        <subfield code="a">TUW</subfield>
        <subfield code="b">ger</subfield>
        <subfield code="c">VL-NEW</subfield>
        <subfield code="d">AT-UBTUW</subfield>
        <subfield code="e">rda</subfield>
        </datafield>
        <datafield tag="044" ind1=" " ind2=" ">
        <subfield code="c">XA-AT</subfield>
        </datafield>
        <datafield tag="090" ind1=" " ind2=" ">
        <subfield code="h">g</subfield>
        </datafield>
        <datafield tag="100" ind1="1" ind2=" ">
        <subfield code="a">Adams, Gunnar</subfield>
        <subfield code="4">aut</subfield>
        </datafield>
        <datafield tag="245" ind1="1" ind2="0">
        <subfield code="a">Dawn of Operator Obligations</subfield>
        <subfield code="b">Estate Independent Benchmarking for Large Real Estate Portfolios</subfield>
        </datafield>
        <datafield tag="264" ind1=" " ind2="1">
        <subfield code="a">Wien</subfield>
        <subfield code="b">Technische Universität Wien</subfield>
        <subfield code="c">2019</subfield>
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
        <datafield tag="520" ind1=" " ind2=" ">
        <subfield code="a">eng: Even though operator obligations are not new to Facility Management professionals, a constant struggle within handling these can be observed. This applies particularly for large heterogeneous real estate portfolios. The large diversity of estates, each with an individual background relating to contractual relations, user demands, building service engineering and different competent bodies, have proven traditional benchmarking approaches to be not expedient on this very occasion. Therefore, we did develop a new process to benchmark operator obligations especially handy for large portfolios. Facing interface problems within the Facility Management organisation, a bottom-up approach allowed us to meet a required insensitivity for such problems by interviewing mainly the executing teams and crosschecking these results while following the path of delegation upwards. The operator organisation’s structure with different technical departments has been taken into account by allocating the operator obligations to cost types according to the german DIN 276: Kosten im Bauwesen. In combination with facilities lists from CAFM-software, this approach made an estate based analysis obsolete and therefore reduced the benchmarking expenditure. The implementation of this process resulted in the evaluation of over 3000 data points during a time span of four years and delivered a sufficiently accurate statement on operator obligations, pointing out not handled obligations, organisational problems and insufficient control of third-party facility service providers equally.</subfield>
        </datafield>
        <datafield tag="542" ind1=" " ind2=" ">
        <subfield code="a">Unter einer CC-Lizenz, Details siehe Link</subfield>
        <subfield code="f">CC BY-NC 2.0 DE</subfield>
        <subfield code="2">cc</subfield>
        <subfield code="u">https://creativecommons.org/licenses/by-nc/2.0/de/deed.en</subfield>
        </datafield>
        <datafield tag="700" ind1="1" ind2=" ">
        <subfield code="a">Lennerts, Kunibert</subfield>
        <subfield code="4">aut</subfield>
        </datafield>
        <datafield tag="700" ind1="1" ind2=" ">
        <subfield code="a">Vöst, Sebastian</subfield>
        <subfield code="4">aut</subfield>
        </datafield>
        <datafield tag="773" ind1="0" ind2="8">
        <subfield code="i">Enthalten in</subfield>
        <subfield code="t">IFM Journal</subfield>
        <subfield code="d">2019</subfield>
        <subfield code="g">Jahrgang (2019), Heft 19, Seiten 8-27</subfield>
        <subfield code="w">(AT-OBV)AC13348910</subfield>
        </datafield>
        <datafield tag="856" ind1="4" ind2="0">
        <subfield code="m">V:AT-OBV;B:AT-V:AT-OBV;B:AT-UBTUW</subfield>
        <subfield code="q">text/html</subfield>
        <subfield code="u">https://resolver.obvsg.at/urn:nbn:at:at-ubtuw:4-3370</subfield>
        <subfield code="x">TUW</subfield>
        <subfield code="3">Volltext</subfield>
        <subfield code="o">OBV-EDOC-VL</subfield>
        </datafield>
        <datafield tag="970" ind1="2" ind2=" ">
        <subfield code="a"> TUW</subfield>
        <subfield code="d">OA-ARTICLE</subfield>
        </datafield>
        <datafield tag="970" ind1="9" ind2=" ">
        <subfield code="m">V:AT-OBV;B:AT-V:AT-OBV;B:AT-UBTUW</subfield>
        <subfield code="q">application/pdf</subfield>
        <subfield code="u">http://media.obvsg.at/AC15504337-2001</subfield>
        <subfield code="x">TUW</subfield>
        <subfield code="3">Volltext</subfield>
        </datafield>
        <datafield tag="974" ind1="0" ind2="s">
        <subfield code="F">030</subfield>
        <subfield code="A">a|1urr|||||||</subfield>
        </datafield>
        <datafield tag="974" ind1="0" ind2="s">
        <subfield code="F">050</subfield>
        <subfield code="A">||||||||g|||||</subfield>
        </datafield>
        <datafield tag="974" ind1="0" ind2="s">
        <subfield code="F">051</subfield>
        <subfield code="A">at||w|||</subfield>
        </datafield>
    </record>
    </bib>
    """

    return text
