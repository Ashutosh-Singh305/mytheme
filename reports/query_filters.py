from django.db import models
from django.apps import apps

# ---------------------------------------------------------------------------
# Lookup map for filter operations
# ---------------------------------------------------------------------------
LOOKUP_MAP = {
    "eq": "exact",
    "neq": "exact",
    "lt": "lt",
    "lte": "lte",
    "gt": "gt",
    "gte": "gte",
    "contains": "icontains",     # correct: case-insensitive
    "not_contains": "icontains",
    "startswith": "startswith",
    "endswith": "endswith",
    "isnull": "isnull",
    "in": "in",
    "not_in": "in",
    
    # Date-specific operators
    # 'today': 'Today',
    # 'yesterday': 'Yesterday',
    # '7_days': 'Last 7 days',
    # '30_days': 'Last 30 days',
    # 'this_month': 'This month',
    # 'last_month': 'Last month',
}


# ---------------------------------------------------------------------------
# Filter Normalizer
# Converts any filter format → uniform dict: {field, op, value}
# ---------------------------------------------------------------------------
def _normalize_filter_dict(f):
    # -----------------------------
    # Case 1: FilterSpec object
    # -----------------------------
    if hasattr(f, "field") or hasattr(f, "op") or hasattr(f, "value"):
        return {
            "id": getattr(f, "id", None),   # 🔥 ADD THIS
            "field": getattr(f, "field", None),
            "op": getattr(f, "op", "eq"),
            "value": getattr(f, "value", None),
        }

    # -----------------------------
    # Case 2: dict format
    # -----------------------------
    if isinstance(f, dict):
        field = f.get("field")
        value = f.get("value")
        fid = f.get("id")   # 🔥 ALWAYS CAPTURE ID

        if "op" in f:
            return {
                "id": fid,   # 🔥 KEEP ID
                "field": field,
                "op": f.get("op") or "eq",
                "value": value,
            }

        if "condition" in f:
            cond = f.get("condition")
            return {
                "id": fid,   # 🔥 KEEP ID
                "field": field,
                "op": cond or "eq",
                "value": value,
            }

    # -----------------------------
    # Fallback
    # -----------------------------
    if isinstance(f, dict):
        return {
            "id": f.get("id"),   # 🔥 KEEP ID
            "field": f.get("field"),
            "op": f.get("op") or "eq",
            "value": f.get("value"),
        }

    return {
        "id": None,
        "field": None,
        "op": "eq",
        "value": None,
    }


# ---------------------------------------------------------------------------
# Queryset Builder with SAFE lookup handling
# ---------------------------------------------------------------------------
from datetime import timedelta
from django.utils.timezone import now

def build_filtered_queryset(model, filters):
    filter_kwargs = {}
    neq_filters = []
    not_contains_filters = []
    not_in_filters = []

    for f in filters:
        f = _normalize_filter_dict(f)

        field = f["field"]
        op = f["op"]
        val = f["value"]

        if not field:
            continue

        # get field object
        try:
            field_obj = model._meta.get_field(field)
        except Exception:
            field_obj = None

        # ----------------------------
        # DATE OPERATORS (FIXED 🔥)
        # ----------------------------
        if field_obj and isinstance(field_obj, (models.DateField, models.DateTimeField)):

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

                # DateTimeField
                if isinstance(field_obj, models.DateTimeField):
                    filter_kwargs[f"{field}__date__range"] = (start, end)
                else:
                    filter_kwargs[f"{field}__range"] = (start, end)

                continue  # 🔥 IMPORTANT

        # ----------------------------
        # LOOKUP
        # ----------------------------
        lookup = LOOKUP_MAP.get(op)
        if not lookup:
            lookup = "exact"

        # neq
        if op == "neq":
            neq_filters.append((field, val))
            continue

        # not contains
        if op == "not_contains":
            not_contains_filters.append((field, val))
            continue

        # isnull
        if op == "isnull":
            filter_kwargs[f"{field}__isnull"] = str(val).lower() in ("1", "true", "yes")
            continue

        # skip blank
        if val in (None, ""):
            continue

        # NOT IN
        if op == "not_in":
            arr = [v.strip() for v in str(val).split(",") if v.strip()]
            not_in_filters.append((field, arr))
            continue

        # IN
        if op == "in":
            arr = [v.strip() for v in str(val).split(",") if v.strip()]
            filter_kwargs[f"{field}__in"] = arr
            continue

        # ----------------------------
        # TYPE CAST
        # ----------------------------
        try:
            if isinstance(field_obj, models.IntegerField):
                val = int(val)
            elif isinstance(field_obj, models.FloatField):
                val = float(val)
            elif isinstance(field_obj, models.BooleanField):
                val = str(val).lower() in ("1", "true", "yes")
        except Exception:
            pass

        filter_kwargs[f"{field}__{lookup}"] = val

    # ----------------------------
    # APPLY FILTERS
    # ----------------------------
    qs = model.objects.filter(**filter_kwargs)

    for field, val in neq_filters:
        qs = qs.exclude(**{f"{field}__exact": val})

    for field, val in not_contains_filters:
        qs = qs.exclude(**{f"{field}__icontains": val})

    for field, arr in not_in_filters:
        qs = qs.exclude(**{f"{field}__in": arr})

    return qs