from django.db.models import Q
from django import template
from cms import models as cms_models

register = template.Library()


@register.simple_tag
def tag_get_sub_nav_items(top_nav_item,language):
    return cms_models.NavigationItem.objects \
        .filter(top_level_nav=top_nav_item) \
        .filter(Q(language=None) | Q(language=language)) \
        .order_by('sequence')
