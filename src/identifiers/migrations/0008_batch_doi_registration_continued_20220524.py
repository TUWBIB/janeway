# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2022-03-15 20:06
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion

def migrate_current_crossref_deposit_identifiers(apps, schema_editor):
    CrossrefDeposit = apps.get_model("identifiers", "CrossrefDeposit")
    for crossref_deposit in CrossrefDeposit.objects.all().order_by('date_time'):
        if crossref_deposit.identifier:
            CrossrefStatus = apps.get_model("identifiers", "CrossrefStatus")
            crossref_status, created = CrossrefStatus.objects.get_or_create(
                identifier=crossref_deposit.identifier
            )
            # print('\n\n\n')
            # print(crossref_status.identifier.identifier)
            # print('CrossrefStatus attached to doi:', crossref_status.identifier.identifier)
            # print('CrossrefStatus message before ifs:', crossref_status.message)
            if crossref_deposit.queued:
                crossref_status.message = 'queued'
            elif crossref_deposit.success:
                if not crossref_deposit.citation_success:
                    crossref_status.message = 'registered_but_citation_problems'
                else:
                    crossref_status.message = 'registered'
            elif crossref_deposit.has_result:
                crossref_status.message = 'failed'
            else:
                crossref_status.message = ''

            crossref_status.deposits.add(crossref_deposit)
            crossref_status.save()
            # print('CrossrefStatus message  after ifs:', crossref_status.message)
            # print('CrossrefDeposit with identifier still attached:', crossref_deposit.identifier.identifier)
            crossref_deposit.identifier = None
            crossref_deposit.save()
            # print('CrossrefDeposit with identifier removed:', crossref_deposit.identifier)
            # print('CrossrefDeposit result text:', crossref_deposit.result_text)

class Migration(migrations.Migration):
    dependencies = [
        ('identifiers', '0007_batch_doi_registration_20220315'),
    ]

    operations = [
        migrations.RunPython(migrate_current_crossref_deposit_identifiers, reverse_code=migrations.RunPython.noop),
    ]
