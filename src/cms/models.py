__copyright__ = "Copyright 2017 Birkbeck, University of London"
__author__ = "Martin Paul Eve & Andy Byers"
__license__ = "AGPL v3"
__maintainer__ = "Birkbeck Centre for Technology and Publishing"


from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import ugettext_lazy as _
from hvad.models import TranslatableModel, TranslatedFields

from utils.logic import build_url_for_request

LANGUAGE_CHOICES = (
    (u'en', _('English')),
    (u'de', _('German')),
    (u'fr', _('French')),
    (u'hide', _('<Hide>')),
)

class Page(TranslatableModel):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, related_name='page_content', null=True)
    object_id = models.PositiveIntegerField(blank=True, null=True)
    object = GenericForeignKey('content_type', 'object_id')

    name = models.CharField(max_length=300, help_text="Page name displayed in the URL bar eg. about or contact")
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


class NavigationItem(TranslatableModel):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, related_name='nav_content', null=True)
    object_id = models.PositiveIntegerField(blank=True, null=True)
    object = GenericForeignKey('content_type', 'object_id')

    link = models.CharField(max_length=100)
    is_external = models.BooleanField(default=False)
    sequence = models.IntegerField(default=99)
    page = models.ForeignKey(Page, blank=True, null=True)
    has_sub_nav = models.BooleanField(default=False, verbose_name="Has Sub Navigation")
    top_level_nav = models.ForeignKey("self", blank=True, null=True, verbose_name="Top Level Nav Item")
    language = models.CharField(max_length=200, blank=True, null=True,
        choices=LANGUAGE_CHOICES,
        help_text=_('Language for which this nav item is displayed, leave empty if item is to be shown regardless of language'))

    translations = TranslatedFields(
        link_name = models.CharField(max_length=100)
    )

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
        return self.build_url_for_request

    @classmethod
    def toggle_collection_nav(cls, issue_type):
        """Toggles a nav item for the given issue_type
        :param `journal.models.IssueType` issue_type: The issue type to toggle
        """

        defaults = {
            "link_name": issue_type.plural_name,
            "link": "/collections/%s" % (issue_type.code),
        }
        content_type = ContentType.objects.get_for_model(issue_type.journal)

        nav, created = cls.objects.language().fallbacks('en').get_or_create(
            content_type=content_type,
            object_id=issue_type.pk,
            defaults=defaults,
        )

        if not created:
            nav.delete()

# returning None implicitly disables collections on a whole
# problem is that nav items created for journal B (id=2) are
# read as collection for journal A (id=1)
# live with this even if object_ids in cms_navigationitem are not as intended


    @classmethod
    def get_content_nav_for_journal(cls, journal):
        return None

#        for issue_type in journal.issuetype_set.filter(
#            ~Q(code="issue") # Issues have their own navigation
#        ):
#            try:
#                content_type = ContentType.objects.get_for_model(
#                    issue_type.journal)
#
#                yield issue_type, cls.objects.language().fallbacks('en').get(
#                    content_type=content_type,
#                    object_id=issue_type.pk,
#                )
#            except cls.DoesNotExist:
#                yield issue_type, None
#
