# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2021-10-05 12:13
from __future__ import unicode_literals

from django.db import migrations, models

from journal.views import keyword

lookup = {
"4": "460,461,462,463",
"5": "464,465,466",
"6": "467,468,469,470",
"7": "471,472,473,474,470",
"8": "467,475,472,476,477",
"9": "478,479,472,477",
"13": "480,481,482,462,461",
"14": "483,484,472",
"15": "485,472,486,487",
"16": "488,489,490,491,492",
"17": "470,493,494,491",
"18": "470,493,495",
"22": "467,468,470,469",
"23": "464,470,496,497,466",
"24": "498,470,495,499",
"25": "480,470,500,501,462",
"26": "460,502,503,504,505",
"30": "464,495,506,507,508",
"31": "509,510,511,512",
"32": "513,514,515,516,470",
"33": "467,469,472,462",
"34": "467,461,517,518",
"35": "464,475,497,519",
"39": "464,520,521",
"40": "499,472,522,523,461",
"41": "472,524,475,525",
"42": "460,467,526,527,528",
"46": "460,529,530,531,532",
"47": "513,533,534,535,514",
"48": "536,495,472,537,538",
"49": "464,504,477,475",
"53": "460,539,513,500",
"54": "509,510,507,512,540",
"55": "531,495,470",
"56": "467,541,470,504",
"60": "542,497,475,543,544,545",
"61": "460,546,547,548,549",
"62": "550,551,519,552",
"63": "523,460,504,537,531,475",
"67": "464,553,507,554",
"68": "460,555,556,557,495",
"69": "558,495,559,469",
"70": "464,469,495,560,561",
"74": "472,562,560,563,564",
"75": "460,513,565,566,567",
"76": "467,504,460,568,569,570",
"77": "464,521,515,571",
"78": "460,547,470,504",
"82": "464,543,572,573,470",
"83": "495,504,574,575,576,577,513",
"84": "460,578,579,531,580,523,581,582",
"85": "531,583,584,585,547,470",
"89": "586,587,473,467,588,460",
"90": "460,589,590,591",
"91": "513,592,502,509",
"92": "460,543,593,513,594",
"96": "460,595,596,516,597",
"97": "598,599,600,470",
"98": "460,513,565,564,567",
"99": "601,472,602,475",
"103": "460,543,603",
"104": "499,604,472,462",
"105": "513,564,605,538,606",
"106": "607,486,608,609",
"110": "460,610,504,611,612",
"111": "463,511,613,611,614",
"112": "601,563,472,564,615,594",
"116": "460,486,547,616,617",
"117": "513,577,594,565,613,618,615",
"118": "619,543,472,620,621",
"119": "601,472,622,623,624",
"123": "460,625,613,626,627,628",
"124": "626,629,475,630,631",
"125": "460,632,633,634",
"129": "499,604,472,462",
"130": "460,635,636,637",
"131": "460,638,639,640",
"132": "486,629,641,642,643,615",
"136": "513,644,645,565,564,502,509,646,615",
"137": "647,543,520,512",
"138": "486,631,648,649,650",
"142": "460,504,651,584,652",
"143": "460,504,515,653",
"144": "513,509,535,639",
"148": "115,116,117",
"153": "118,119,120,121,122",
"292": "123,124,125,126,127",
"393": "128,91,129",
"411": "130,131,132",
"412": "133,134,135",
"428": "136,137,138,139,140",
"569": "655,514,656,657,626",
"570": "563,566,658,659,646,605",
"571": "460,629,660,661,662,663",
"572": "463,664,628,511",
}

def repair_order_en(apps, schema_editor):
    Article = apps.get_model('submission', 'Article')
    Keyword = apps.get_model('submission', 'Keyword')
    KeywordArticle = apps.get_model('submission', 'KeywordArticle')

    for a in Article.objects.all():
        for kwa in KeywordArticle.objects.filter(article=a):
            kwa.delete()
        s = lookup.get(str(a.id),None)
        if s is not None:
            print (a.id)
            l = s.split(',')
            order = 0        
            for kw_idx in l:
                order += 1
                kw = Keyword()
                kw.pk = int(kw_idx)
                kwa = KeywordArticle.objects.create(
                    article = a,
                    keyword = kw,
                    order = order,
                    )

class Migration(migrations.Migration):

    dependencies = [
        ('submission', '9002_tuw_external_sync'),
    ]

    operations = [
        migrations.RunPython(repair_order_en, reverse_code=migrations.RunPython.noop),
    ]