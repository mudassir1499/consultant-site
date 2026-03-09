from django import template

register = template.Library()


@register.filter(name='split')
def split_string(value, delimiter=','):
    """Split a string by delimiter and return a list."""
    if not value:
        return []
    return [item.strip() for item in value.split(delimiter)]
