# Generated by Django 4.2 on 2024-07-18 15:38

import core.model_utils
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('repository', '0044_alter_repositoryfield_help_text'),
    ]

    operations = [
        migrations.AddField(
            model_name='historicalrepository',
            name='review_submission_text',
            field=core.model_utils.JanewayBleachField(blank=True, default='<p>Please review your submission carefully. Make any necessary changes to ensure that all information is accurate and complete.</p><p>When you are satisfied with your review click the button below to finalize your submission.</p>', help_text='Text that displays on the review page just before the author completes their submission.'),
        ),
        migrations.AddField(
            model_name='repository',
            name='review_submission_text',
            field=core.model_utils.JanewayBleachField(blank=True, default='<p>Please review your submission carefully. Make any necessary changes to ensure that all information is accurate and complete.</p><p>When you are satisfied with your review click the button below to finalize your submission.</p>', help_text='Text that displays on the review page just before the author completes their submission.'),
        ),
    ]
