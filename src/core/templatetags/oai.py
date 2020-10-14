from django import template

register = template.Library()

@register.filter('oai_datestamp')
def oai_datestamp(date):
    return date.replace(microsecond=0).isoformat()[:-6]+'Z'
