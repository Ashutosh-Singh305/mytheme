# reports/templatetags/report_tags.py
from django import template

register = template.Library()

@register.filter
def get_item(d, k):
    """Safe dict.get for templates."""
    if d is None:
        return None
    try:
        return d.get(k)
    except Exception:
        return None

@register.simple_tag
def cell_key(rk, ck):
    """
    Build the exact key your engine uses for matrix cells:
    f"{rk}|{ck}" where rk/ck are tuples of (alias, value) pairs.
    """
    return f"{rk}|{ck}"

@register.filter
def tuple_label(key_tuple):
    """
    Turn a tuple of (alias, value) pairs into a human label.
    Example:
      (('status','follow_up'),)         -> 'follow_up'
      (('a','X'),('b','Y'))             -> 'X / Y'
      ()                                 -> '—'
    """
    if not key_tuple:
        return "—"
    try:
        parts = [str(v) for (_a, v) in key_tuple]
        return " / ".join(parts) if parts else "—"
    except Exception:
        return str(key_tuple)

@register.filter
def coalesce(a, b):
    """Return a if it's truthy (including 0), else b."""
    return a if a is not None else b
