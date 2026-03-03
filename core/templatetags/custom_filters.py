from django import template
register = template.Library()

from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    if isinstance(dictionary, dict):
        # If the dictionary values are strings (final level), return empty string
        # If the dictionary values are dictionaries (intermediate level), return empty dict
        sample_value = next(iter(dictionary.values())) if dictionary else None
        if isinstance(sample_value, str):
            return dictionary.get(key, "")
        else:
            return dictionary.get(key, {})
    return {}

@register.filter
def add(value, arg):
    try:
        return int(value) + int(arg)
    except (ValueError, TypeError):
        return value

@register.filter
def divide(value, arg):
    try:
        return round(float(value) / float(arg), 2)
    except:
        return 0

@register.filter
def subject_color(subject_name):
    colors = ['#FFD700', '#90EE90', '#FFB6C1', '#ADD8E6', '#FFA07A', '#E6E6FA', '#FF8C00', '#20B2AA', '#DDA0DD']
    return colors[abs(hash(subject_name)) % len(colors)]
# core/templatetags/custom_filters.py



@register.filter
def get_entry(dictionary, day, slot, batch):
    # Not used here but can be made for advanced usage
    return dictionary.get(day, {}).get(slot, {}).get(batch, {})
@register.filter
def stringformat(value, arg):
    # fallback for '|stringformat:"s"' if not already available
    return str(value)