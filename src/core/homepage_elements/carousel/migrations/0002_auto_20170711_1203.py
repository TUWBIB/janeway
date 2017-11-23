# -*- coding: utf-8 -*-
# Generated by Django 1.9.13 on 2017-07-11 12:03
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('core', '0001_initial'),
        ('submission', '0001_initial'),
        ('carousel', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='carouselobject',
            name='articleID',
            field=models.ManyToManyField(blank=True, null=True, to='submission.Article'),
        ),
        migrations.AddField(
            model_name='carouselobject',
            name='large_image_file',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='core.File'),
        ),
        migrations.AddField(
            model_name='carousel',
            name='articles',
            field=models.ManyToManyField(blank=True, null=True, related_name='articles', to='submission.Article'),
        ),
    ]
