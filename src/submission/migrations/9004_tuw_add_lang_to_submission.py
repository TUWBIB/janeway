# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2021-10-05 12:13
from __future__ import unicode_literals

from django.db import migrations, models

from journal.views import keyword

def migrate_keywords_de(apps, schema_editor):
    Article = apps.get_model('submission', 'Article')
    Keyword = apps.get_model('submission', 'Keyword')
    KeywordArticle = apps.get_model('submission', 'KeywordArticle')

    for a in Article.objects.all():
        for kw_de in a.keywords_de.all().order_by('submission_article_keywords_de.id'):
            kw = Keyword.objects.create(
				word = kw_de.word,
				language = 'de',
			)
            try:
                latest = KeywordArticle.objects.filter(article=a).latest("order").order
            except KeywordArticle.DoesNotExist:
                latest = 0
            latest += 1
            kw_a = KeywordArticle.objects.create(
                article = a,
                keyword = kw,
                order = latest,
            )
class Migration(migrations.Migration):

    dependencies = [
        ('submission', '9003_tuw_repair_order'),
    ]

    operations = [
        migrations.AddField(
            model_name='keyword',
            name='language',
            field=models.CharField(default='en', max_length=2, null=False),
            preserve_default=False,
        ),
        migrations.RunPython(migrate_keywords_de, reverse_code=migrations.RunPython.noop),
    ]
