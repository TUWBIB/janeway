# Generated by Django 3.2.16 on 2023-04-18 10:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('review', '0018_auto_20230120_1546'),
    ]

    operations = [
        migrations.AlterField(
            model_name='decisiondraft',
            name='decision',
            field=models.CharField(choices=[('accept', 'Accept Without Revisions'), ('minor_revisions', 'Minor Revisions Required'), ('major_revisions', 'Major Revisions Required'), ('reject', 'Reject'), ('none', 'No Recommendation')], max_length=100, verbose_name='Draft Decision'),
        ),
        migrations.AlterField(
            model_name='reviewassignment',
            name='decision',
            field=models.CharField(blank=True, choices=[('accept', 'Accept Without Revisions'), ('minor_revisions', 'Minor Revisions Required'), ('major_revisions', 'Major Revisions Required'), ('reject', 'Reject'), ('none', 'No Recommendation')], max_length=20, null=True, verbose_name='Recommendation'),
        ),
    ]
