# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2022-03-21 13:06
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('submission', '0066_article_issn_override'),
    ]

    operations = [
        migrations.AddField(
            model_name='article',
            name='last_modified',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name='frozenauthor',
            name='last_modified',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name='licence',
            name='last_modified',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name='publishernote',
            name='last_modified',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name='section',
            name='last_modified',
            field=models.DateTimeField(auto_now=True),
        ),
    ]
