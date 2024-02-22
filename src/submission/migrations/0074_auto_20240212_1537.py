# Generated by Django 3.2.20 on 2024-02-12 15:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('submission', '0073_bleach_title_20230523_1804'),
    ]

    operations = [
        migrations.AddField(
            model_name='submissionconfiguration',
            name='submission_file_text_cy',
            field=models.CharField(default='Manuscript File', help_text='During submission the author will be asked to upload a filethat is considered the main text of the article. You can usethis field to change the label for that file in submission.', max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='submissionconfiguration',
            name='submission_file_text_de',
            field=models.CharField(default='Manuscript File', help_text='During submission the author will be asked to upload a filethat is considered the main text of the article. You can usethis field to change the label for that file in submission.', max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='submissionconfiguration',
            name='submission_file_text_en',
            field=models.CharField(default='Manuscript File', help_text='During submission the author will be asked to upload a filethat is considered the main text of the article. You can usethis field to change the label for that file in submission.', max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='submissionconfiguration',
            name='submission_file_text_en_us',
            field=models.CharField(default='Manuscript File', help_text='During submission the author will be asked to upload a filethat is considered the main text of the article. You can usethis field to change the label for that file in submission.', max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='submissionconfiguration',
            name='submission_file_text_fr',
            field=models.CharField(default='Manuscript File', help_text='During submission the author will be asked to upload a filethat is considered the main text of the article. You can usethis field to change the label for that file in submission.', max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='submissionconfiguration',
            name='submission_file_text_nl',
            field=models.CharField(default='Manuscript File', help_text='During submission the author will be asked to upload a filethat is considered the main text of the article. You can usethis field to change the label for that file in submission.', max_length=255, null=True),
        ),
    ]
