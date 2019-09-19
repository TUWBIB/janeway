# -*- coding: utf-8 -*-
# Generated by Django 1.11.22 on 2019-08-05 15:12
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('journal', '0031_issue_old_issue_type'),
    ]

    operations = [
        migrations.CreateModel(
            name='IssueType',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=255)),
                ('pretty_name', models.CharField(max_length=255)),
                ('custom_plural', models.CharField(blank=True, max_length=255, null=True)),
                ('journal', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='journal.Journal')),
            ],
        ),
        migrations.AlterField(
            model_name='issue',
            name='issue_type',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='journal.IssueType'),
        ),
        migrations.AlterField(
            model_name='issue',
            name='old_issue_type',
            field=models.CharField(blank=True, choices=[('Issue', 'Issue'), ('Collection', 'Collection')], default='Issue', max_length=200, null=True),
        ),
        migrations.AlterUniqueTogether(
            name='issuetype',
            unique_together=set([('journal', 'code')]),
        ),
    ]
