from django import template
register = template.Library()

from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    print(f"GET_ITEM FILTER: key={key} from dict={dictionary}")
    if isinstance(dictionary, dict):
        return dictionary.get(key, {})
    return {}

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