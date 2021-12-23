__copyright__ = "Copyright 2017 Birkbeck, University of London"
__author__ = "Martin Paul Eve & Andy Byers"
__license__ = "AGPL v3"
__maintainer__ = "Birkbeck Centre for Technology and Publishing"

import os

from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import ugettext_lazy as _
from django.conf import settings

from core.file_system import JanewayFileSystemStorage
from utils.logic import build_url_for_request

LANGUAGE_CHOICES = (
    (u'en', _('English')),
    (u'de', _('German')),
    (u'fr', _('French')),
    (u'hide', _('<Hide>')),
)

class Page(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, related_name='page_content', null=True)
    object_id = models.PositiveIntegerField(blank=True, null=True)
    object = GenericForeignKey('content_type', 'object_id')

    name = models.CharField(
        max_length=300,
        help_text="Page name displayed in the URL bar eg. about or contact",
        verbose_name="URL Name"
    )
    display_name = models.CharField(
        max_length=100,
        help_text='Name of the page, max 100 chars, displayed '
                  'in the nav and on the header of the page eg. '
                  'About or Contact',
    )
    content = models.TextField(null=True, blank=True)
    is_markdown = models.BooleanField(default=True)
    edited = models.DateTimeField(auto_now=timezone.now)

    translations = TranslatedFields(
        display_name = models.CharField(max_length=100, help_text=_('Name of the page, max 100 chars, displayed '
                                                                'in the nav and on the header of the page eg. '
                                                                'About or Contact')),
        content = models.TextField(null=True, blank=True)
    )

    def __str__(self):
        return u'{0} - {1}'.format(self.content_type, self.display_name)


class NavigationItem(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, related_name='nav_content', null=True)
    object_id = models.PositiveIntegerField(blank=True, null=True)
    object = GenericForeignKey('content_type', 'object_id')

    link_name = models.CharField(max_length=100)
    link = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )
    is_external = models.BooleanField(default=False)
    sequence = models.IntegerField(default=99)
    page = models.ForeignKey(Page, blank=True, null=True)
    has_sub_nav = models.BooleanField(default=False, verbose_name="Has Sub Navigation")
    top_level_nav = models.ForeignKey("self", blank=True, null=True, verbose_name="Top Level Nav Item")
    language = models.CharField(max_length=200, blank=True, null=True,
        choices=LANGUAGE_CHOICES,
        help_text=_('Language for which this nav item is displayed, leave empty if item is to be shown regardless of language'))
    class Meta:
        ordering = ('sequence',)

    def __str__(self):
        return self.link_name

    def sub_nav_items(self):
        return NavigationItem.objects.language().fallbacks('en').filter(top_level_nav=self)

    @property
    def build_url_for_request(self):
        if self.is_external:
            return self.link
        else:
            return build_url_for_request(path=self.link)

    @property
    def url(self):
        #alias for backwards compatibility with templates
        if self.link:
            return self.build_url_for_request
        return ''

    @classmethod
    def toggle_collection_nav(cls, issue_type):
        """Toggles a nav item for the given issue_type
        :param `journal.models.IssueType` issue_type: The issue type to toggle
        """

        defaults = {
            "link": "/collections/%s" % (issue_type.code),
        }
        content_type = ContentType.objects.get_for_model(issue_type.journal)

        nav, created = cls.objects.language().fallbacks('en').get_or_create(
            content_type=content_type,
            object_id=issue_type.journal.pk,
            link_name=issue_type.plural_name,
            defaults=defaults,
        )

        if not created:
            nav.delete()

# returning None implicitly disables collections on a whole
# problem is that nav items created for journal B (id=2) are
# read as collection for journal A (id=1)
# live with this even if object_ids in cms_navigationitem are not as intended


    @classmethod
    def get_issue_types_for_nav(cls, journal):
        return None

#        for issue_type in journal.issuetype_set.filter(
#            ~Q(code="issue") # Issues have their own navigation
#        ):
#            content_type = ContentType.objects.get_for_model(
#                issue_type.journal)
#            if not cls.objects.language().fallbacks('en').filter(
#                content_type=content_type,
#                object_id=issue_type.journal.pk,
#                link_name=issue_type.plural_name,
#            ).exists():
#                yield issue_type
        for issue_type in journal.issuetype_set.filter(
            ~Q(code="issue") # Issues have their own navigation
        ):
            content_type = ContentType.objects.get_for_model(
                issue_type.journal)
            if not cls.objects.filter(
                content_type=content_type,
                object_id=issue_type.journal.pk,
                link_name=issue_type.plural_name,
            ).exists():
                yield issue_type


class SubmissionItem(models.Model):
    """
    Model containing information to render the Submission page.
    SubmissionItems is registered for translation in cms.translation.
    """
    journal = models.ForeignKey('journal.Journal')
    title = models.CharField(max_length=255)
    text = models.TextField(blank=True, null=True)
    order = models.IntegerField(default=99)
    existing_setting = models.ForeignKey('core.Setting', blank=True, null=True)

    class Meta:
        ordering = ('order', 'title')
        unique_together = (('journal', 'existing_setting'), ('journal', 'title'))

    def get_display_text(self):
        if self.existing_setting:
            return self.journal.get_setting(
                self.existing_setting.group.name,
                self.existing_setting.name,
            )
        else:
            return self.text

    def __str__(self):
        return "{journal} {title} - {setting}".format(
            journal=self.journal,
            title=self.title,
            setting=self.existing_setting,
        )


def upload_to_media_files(instance, filename):
    if instance.journal:
        return "journals/{}/{}".format(instance.journal.pk, filename)
    else:
        return "press/{}".format(filename)


class MediaFile(models.Model):
    label = models.CharField(max_length=255)
    file = models.FileField(
        upload_to=upload_to_media_files,
        storage=JanewayFileSystemStorage())
    journal = models.ForeignKey(
        'journal.Journal',
        null=True,
        blank=True,
    )
    uploaded = models.DateTimeField(
        default=timezone.now,
    )

    def unlink(self):
        try:
            os.unlink(
                self.file.path,
            )
        except FileNotFoundError:
            pass

    @property
    def filename(self):
        return os.path.basename(self.file.name)

    def link(self):
        return build_url_for_request(
            path=self.file.url,
        )
