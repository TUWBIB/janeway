# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2022-06-22 12:39
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('submission', '0069_delete_blank_keywords'),
        ('repository', '0030_merge_20220613_1628'),
    ]

    operations = [
        migrations.AddField(
            model_name='repository',
            name='active_licenses',
            field=models.ManyToManyField(blank=True, to='submission.Licence'),
        ),
    ]
