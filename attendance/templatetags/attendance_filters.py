from django import template

register = template.Library()

@register.filter
def dict_get(d, key):
    if isinstance(d, dict):
        return d.get(key, [])
    return []
@register.filter
def get_item(obj, attr_name):
    return getattr(obj, attr_name, "")

# attendance/templatetags/attendance_filters.py


@register.filter
def get_date(obj, key):
    return getattr(obj, key, "")
