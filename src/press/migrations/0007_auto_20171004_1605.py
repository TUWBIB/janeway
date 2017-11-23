# -*- coding: utf-8 -*-
# Generated by Django 1.11.5 on 2017-10-04 16:05
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('press', '0006_press_preprints_about'),
    ]

    operations = [
        migrations.AddField(
            model_name='press',
            name='preprint_pdf_only',
            field=models.BooleanField(default=True, help_text='Forces manuscript files to be PDFs for Preprints.'),
        ),
        migrations.AddField(
            model_name='press',
            name='preprint_start',
            field=models.TextField(blank=True, null=True),
        ),
    ]
