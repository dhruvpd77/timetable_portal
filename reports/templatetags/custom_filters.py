from django import template
register = template.Library()


@register.filter
def get_item(dictionary, key):
    if isinstance(dictionary, dict):
        return dictionary.get(key, '')
    elif hasattr(dictionary, '__getitem__'):
        try:
            return dictionary[key]
        except (KeyError, IndexError, TypeError):
            return ''
    return ''
dict_get = get_item
register.filter('dict_get', dict_get)




@register.filter
def pluck(list_of_dicts, key):
    return [d.get(key, "") for d in list_of_dicts]
import re
@register.filter
def slugify(value):
    return re.sub(r'[^a-zA-Z0-9]+', '-', value).strip('-').lower()


@register.filter
def keys(d):
    """Return keys of a dict (for use in for loop)"""
    if isinstance(d, dict):
        return d.keys()
    return []
@register.filter
def items(d):
    """Return items of the dict."""
    if isinstance(d, dict):
        return d.items()
    return []