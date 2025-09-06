from django import template
register = template.Library()

@register.filter
def dict_get(d, key):
    if isinstance(d, dict):
        return d.get(key, "")
    return ""

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)