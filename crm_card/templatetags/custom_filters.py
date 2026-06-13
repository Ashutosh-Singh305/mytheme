# crm/templatetags/custom_filters.py

from django import template
register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter
def get_dynamic_value(obj, attr):
    """Return attribute value on a model instance."""
    return getattr(obj, attr, None)

@register.filter
def get_field(form, field_name):
    """Safely access a form field dynamically by name."""
    try:
        return form[field_name]
    except KeyError:
        return None