# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2023-02-14 18:09
from __future__ import unicode_literals

from django.db import migrations, models


def fix_bad_galley_type(apps, schema_editor):
    """ Fixes records that have mistakenly set their galley_type as 'view' """
    ArticleAccess = apps.get_model("metrics", "ArticleAccess")
    Article = apps.get_model("submission", "Article")
    for galley_type in ["html", "xml", "image"]: # Order matters
        print("Fixing Access records of type '%s'" % galley_type)
        # First, fix articles with no render_galley:
        articles = Article.objects.filter(
            stage="Published",
            render_galley__isnull=True,
            galley__type=galley_type,
        )
        for article in articles:
            article.render_galley = article.galley_set.filter(type=galley_type).first()
            article.save()

        # Then fix bad records for this galley type
        ArticleAccess.objects.filter(
            article__render_galley__type=galley_type,
            galley_type="view",
        ).update(galley_type=galley_type)

    # Set remaining ones to None
    ArticleAccess.objects.filter(
        galley_type="view",
    ).update(galley_type=None)


def rollback(apps, schema_editor):
    ArticleAccess = apps.get_model("metrics", "ArticleAccess")
    ArticleAccess.objects.filter(
        galley_type=None,
    ).update(galley_type="view")


class Migration(migrations.Migration):

    dependencies = [
        ('metrics', '9000_tuw_add_explicit_ip'),
    ]

    operations = [
        migrations.AlterField(
            model_name='articleaccess',
            name='galley_type',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.RunPython(
            fix_bad_galley_type,
            reverse_code=rollback,
        ),
    ]