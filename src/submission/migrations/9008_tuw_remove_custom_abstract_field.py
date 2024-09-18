from __future__ import unicode_literals

from django.db import migrations, models
from django.utils.translation import gettext_lazy as _

class Migration(migrations.Migration):

    dependencies = [
        ('submission', '0080_frozen_author_bleach_20240507_1350'),
    ]

    operations = [
        migrations.RunSQL("UPDATE submission_article SET abstract_de = abstract_de_tuw WHERE (abstract_de is NULL OR abstract_de = '') AND (abstract_de_tuw IS NOT NULL AND abstract_de_tuw <> '') OR id IN (67,69,70,74,77,89,98,99,665);"),
        migrations.RemoveField(
            model_name='article',
            name='abstract_de_tuw',
        ),
    ]
