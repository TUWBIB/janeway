# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2021-12-09 13:50
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0051_auto_20210607_1100'),
    ]

    operations = [
        migrations.AddField(
            model_name='account',
            name='gndid',
            field=models.CharField(blank=True, max_length=40, null=True, verbose_name='GND iD'),
        ),
    ]
