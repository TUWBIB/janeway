# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2022-05-22 07:52
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion
import django.db.models.manager

class Migration(migrations.Migration):

    dependencies = [
        ('submission', '0062_auto_20211013_1133'),
    ]

    operations = [
        migrations.CreateModel(
            name='CitedReference',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text', models.CharField(max_length=2000)),
            ],
        ),
        migrations.AddField(
            model_name='citedreference',
            name='article',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='submission.Article'),
        ),
    ]