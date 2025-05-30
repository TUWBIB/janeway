from django import template

register = template.Library()


@register.filter
def latex_conform(value):
    return "{%s}" % value

# TUW
# assuming page range is in format a-b... '-' needs to be doubled 
@register.filter
def latex_conform_page_range(value):
    return f"{{{value.replace('-','--')}}}"

# TUW
# there might be carriage returns - x0a - in abstracts
@register.filter
def latex_conform_abstract(value):
    return f"{{{value.replace('\x0a',' ')}}}"



