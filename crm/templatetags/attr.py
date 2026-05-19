from django import template
register = template.Library()

@register.filter
def attr(obj, name):
    """
    Safe attribute getter:
    - If obj is dict → return obj.get(name)
    - Else → return getattr(obj, name)
    """
    if isinstance(obj, dict):
        return obj.get(name, "")

    if isinstance(name, dict):
        # prevent accidental dict-name calls
        return ""

    try:
        return getattr(obj, name, "")
    except Exception:
        return ""



@register.filter
def get_verbose_name(obj, field_name):
    """
    Safe verbose name resolver.
    Supports:
    - field_name as string
    - field_name as dict {"name": ..., "label": ...}
    """

    # If the template passed a dict: extract its "name"
    if isinstance(field_name, dict):
        field_name = field_name.get("name", "")

    # If still not a string, return as is
    if not isinstance(field_name, str):
        return str(field_name)

    # Try model verbose_name
    try:
        return obj._meta.get_field(field_name).verbose_name.title()
    except Exception:
        # Fallback
        return field_name.replace("_", " ").title()


@register.filter
def get_field_value(obj, field_name):
    """
    Returns the value of a field, safely.
    """
    try:
        value = getattr(obj, field_name)
        return value if value not in [None, ""] else "—"
    except Exception:
        return ""
