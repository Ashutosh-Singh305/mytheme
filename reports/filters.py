from typing import Any, Dict, Optional
from django.db import models as djm
from django.db.models import Q
from datetime import timedelta
from django.utils.timezone import now

LOOKUPS = {"eq":"", "neq":"", "lt":"__lt","lte":"__lte","gt":"__gt","gte":"__gte",
           "in":"__in","not_in":"__in", "contains":"__icontains","not_contains":"__icontains",
           "startswith":"__istartswith","endswith":"__iendswith", "isnull":"__isnull","range":"__range"}

def _coerce(field: djm.Field, value: Any):
    if isinstance(field,(djm.IntegerField,djm.BigIntegerField,djm.AutoField)): return int(value)
    if isinstance(field,djm.FloatField): return float(value)
    if isinstance(field,djm.DecimalField): return field.to_python(value)
    if isinstance(field,djm.BooleanField): return str(value).lower() in ("1","true","yes","on")
    return value

def _clean_value(value):
    if value is None:
        return None  # 🔥 IMPORTANT FIX (was "" before)

    if isinstance(value, str):
        value = value.replace("“", "").replace("”", "").strip()

    return value


def build_q(model, rule: Dict[str, Any]) -> Optional[Q]:

    path = rule.get("field")
    op = (rule.get("op") or "eq").lower()
    value = _clean_value(rule.get("value"))

    # RESOLVE FIELD
    field = None
    cur = model
    parts = path.split("__") if path else []

    for i, p in enumerate(parts):
        try:
            f = cur._meta.get_field(p)
        except Exception:
            f = None

        if not f:
            field = None
            break

        if f.is_relation and i < len(parts) - 1:
            cur = f.related_model
        else:
            field = f

    # DATE OPERATORS
    if field and isinstance(field, (djm.DateField, djm.DateTimeField)):

        if not value and op not in (
            "today", "yesterday", "7_days", "30_days", "this_month", "last_month"
        ):
            return None

        today = now().date()

        if op in ("today", "yesterday", "7_days", "30_days", "this_month", "last_month"):

            if op == "today":
                start = end = today

            elif op == "yesterday":
                start = end = today - timedelta(days=1)

            elif op == "7_days":
                start = today - timedelta(days=6)
                end = today

            elif op == "30_days":
                start = today - timedelta(days=29)
                end = today

            elif op == "this_month":
                start = today.replace(day=1)
                end = today

            elif op == "last_month":
                first_this_month = today.replace(day=1)
                last_month_end = first_this_month - timedelta(days=1)
                start = last_month_end.replace(day=1)
                end = last_month_end

            if isinstance(field, djm.DateTimeField):
                return Q(**{f"{path}__date__range": (start, end)})

            return Q(**{f"{path}__range": (start, end)})

    # LOOKUP
    lookup = LOOKUPS.get(op)
    if lookup is None:
        return None

    key = f"{path}{lookup}" if lookup else path

    # SPECIAL: ISNULL HANDLING
    if op == "isnull":

        # Base NULL check
        q = Q(**{f"{path}__isnull": True})

        # Handle Char/Text fields → include blank + whitespace
        if field and isinstance(field, (djm.CharField, djm.TextField)):
            q |= Q(**{path: ""})                    # empty string
            q |= Q(**{f"{path}__regex": r"^\s*$"})  # whitespace only

        return q

    # VALUE HANDLING
    if field:

        if op in ("in", "not_in"):
            seq = value if isinstance(value, (list, tuple)) else [
                v.strip() for v in str(value).split(",") if v.strip()
            ]
            value = [_coerce(field, v) for v in seq]

        elif op == "range":
            if isinstance(value, (list, tuple)) and len(value) == 2:
                a, b = value
            else:
                s = str(value).split(",", 1)
                a = s[0]
                b = s[1] if len(s) > 1 else ""
            value = (_coerce(field, a), _coerce(field, b))

        else:
            value = _coerce(field, value)

    # BUILD QUERY
    q = Q(**{key: value})

    if op in ("neq", "not_in", "not_contains"):
        q = ~q

    return q