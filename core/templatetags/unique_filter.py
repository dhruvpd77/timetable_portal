from django import template

register = template.Library()

@register.filter
def unique(value):
    """Returns only unique values in a list, or an empty list if value is None."""
    if value is None:
        return []
    try:
        return list(dict.fromkeys(value))
    except Exception:
        return []
