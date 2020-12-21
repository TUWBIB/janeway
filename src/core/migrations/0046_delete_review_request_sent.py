# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2020-12-21 13:59
from __future__ import unicode_literals

from django.db import migrations


def delete_settings(apps, schema_editor):
    Setting = apps.get_model('core', 'Setting')
    Setting.objects.filter(
        group__name='general',
        name='review_request_sent',
    ).delete()

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0045_fix_url_emails'),
    ]

    operations = [
        migrations.RunPython(
            delete_settings,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
