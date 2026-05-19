from django import template
register = template.Library()

@register.filter
def get_item(d, k):
    """Safely get d[k] from any object."""
    if isinstance(d, dict):
        return d.get(k, "")
    return ""
