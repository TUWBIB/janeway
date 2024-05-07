# Generated by Django 3.2.16 on 2023-03-22 14:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cms', '0013_navigationitem_extend_to_journals'),
    ]

    # Why two operations with support_copy_paste?
    # The new support_copy_paste field has a default value of True,
    # because we want bleach to work on all new content by default.
    # However, we don't want it to wipe out custom styling in existing
    # fields, so we first create the field on existing objects
    # with default=False.

    operations = [
        migrations.AddField(
            model_name='page',
            name='support_copy_paste',
            field=models.BooleanField(
                default=False,
            ),
        ),
        migrations.AlterField(
            model_name='page',
            name='support_copy_paste',
            field=models.BooleanField(
                default=True,
                help_text='Turn this on if copy-pasting content '
                          'from a word processor, '
                          'or using the toolbar to format text. '
                          'It tells Janeway to clear out formatting '
                          'that does not play nice. '
                          'Turn it off and leave it off if anyone has '
                          'added custom HTML or CSS using the code view, '
                          'since it might remove custom code.',
            ),
        ),
    ]
