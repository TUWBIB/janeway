from __future__ import unicode_literals
from datetime import tzinfo, datetime
from django.db import migrations, models
from submission import models as submission_models


class Migration(migrations.Migration):

    def clean_up_titles(apps, schema_editor):
        articles = submission_models.Article.objects.all()
        for article in articles:
            l = []
            l.append(str(article.pk))
            s = ';'.join(l)
            print(s)
            s = ''
#            s += str(article.pk)
#
#
#            if article.get_doi() is not None:
#                article.datacite_state=submission_models.DATACITE_STATE_FINDABLE
#                article.datacite_ts=datetime(2020,1,1)
#                article.save()

    dependencies = [
        ('submission', '0081_auto_20240927_1021'),
    ]

    operations = [
#        migrations.AddField(
#            model_name='article',
#            name='datacite_state',
#            field=models.CharField(blank=True, choices=[('', ''), ('draft', 'draft'), ('findable', 'findable'), ('registered', 'registered')], max_length=20, null=True),
#        ),
#        migrations.AddField(
#            model_name='article',
#            name='datacite_ts',
#            field=models.DateTimeField(blank=True, null=True),
#        ),
        migrations.RunPython(clean_up_titles),
    ]
