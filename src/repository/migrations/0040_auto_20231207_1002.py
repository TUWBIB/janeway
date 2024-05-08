# Generated by Django 3.2.20 on 2023-12-07 10:02

from django.db import migrations, models


def set_repo_themes(apps, schema_editor):
    """
    For existing repositories we should set the theme back to material.
    """
    Repository = apps.get_model(
        'repository',
        'Repository',
    )
    Repository.objects.all().update(theme='material')


class Migration(migrations.Migration):

    dependencies = [
        ('repository', '0039_alter_preprintversion_title'),
    ]

    operations = [
        migrations.AddField(
            model_name='historicalrepository',
            name='theme',
            field=models.CharField(choices=[('OLH', 'OLH'), ('material', 'material')], default='OLH', max_length=20),
        ),
        migrations.AddField(
            model_name='repository',
            name='theme',
            field=models.CharField(choices=[('OLH', 'OLH'), ('material', 'material')], default='OLH', max_length=20),
        ),
        migrations.AlterField(
            model_name='preprintversion',
            name='title',
            field=models.CharField(blank=True, help_text='Your article title', max_length=300),
        ),
        migrations.RunPython(
            set_repo_themes,
            reverse_code=migrations.RunPython.noop
        ),
    ]