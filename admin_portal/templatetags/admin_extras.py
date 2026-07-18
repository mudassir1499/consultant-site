from django import template

register = template.Library()


@register.filter
def get(dictionary, key):
    """Get a value from a dictionary by key. Usage: {{ mydict|get:mykey }}"""
    if dictionary is None:
        return None
    try:
        return dictionary.get(key)
    except (AttributeError, TypeError):
        return None


@register.filter
def cut(value, arg):
    """Remove all occurrences of arg from value."""
    return str(value).replace(str(arg), '')
