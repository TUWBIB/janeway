# -*- coding: utf-8 -*-
# Generated by Django 1.11.23 on 2019-12-29 17:28
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('cms', '0006_page_translatable_3'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='page',
            name='content_tmp',
        ),
        migrations.RemoveField(
            model_name='page',
            name='display_name_tmp',
        ),
    ]
