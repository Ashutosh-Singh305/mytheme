from datetime import date, datetime
from functools import lru_cache
from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponseBadRequest, HttpResponseForbidden, HttpResponseNotFound, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from crm.context_processors import get_or_create_default_listview
from crm.generic_crud import get_rendered_field, is_field_visible
from crm.models import ListView, ListViewFilter, ListViewField
from crm.choices import LEAD_STATUS_CHOICES, LEAD_TYPE_CHOICES, OPERATORS
import re
from django.contrib import messages
from crm.utils import get_visible_queryset
# for excel export
import datetime
import pandas as pd
from io import BytesIO
import csv
from django.http import HttpResponse
from django.utils.timezone import is_aware
from django.core.exceptions import PermissionDenied
from openpyxl import Workbook
#for date specific operators
from django.utils.timezone import now
from django.utils.timezone import make_aware
from django.utils.timezone import get_current_timezone
from calendar import monthrange
# For Pagination
from math import ceil
from types import SimpleNamespace

# CACHES & HELPERS
@lru_cache(maxsize=256)
def get_model_cached(app_label, model_name):
    return apps.get_model(app_label, model_name)

# Cache field metadata for (model_class, field_name)
FIELD_CACHE = {}
def get_field_cached(model, field_name):
    key = f"{model.__module__}.{model.__name__}.{field_name}"
    if key not in FIELD_CACHE:
        FIELD_CACHE[key] = model._meta.get_field(field_name)
    return FIELD_CACHE[key]

# Utility: list of concrete field names for a model (cached)
MODEL_CONCRETE_FIELDS = {}
def get_concrete_field_names(model):
    key = f"{model.__module__}.{model.__name__}"
    if key not in MODEL_CONCRETE_FIELDS:
        MODEL_CONCRETE_FIELDS[key] = [f.name for f in model._meta.get_fields() if getattr(f, "concrete", False)]
    return MODEL_CONCRETE_FIELDS[key]

# GLOBAL CONSTANTS
OPERATOR_MAP = {
    "eq": ("exact", False),
    "neq": ("exact", True),

    "lt": ("lt", False),
    "lte": ("lte", False),
    "gt": ("gt", False),
    "gte": ("gte", False),

    "contains": ("icontains", False),
    "not_contains": ("icontains", True),

    "startswith": ("istartswith", False),
    "endswith": ("iendswith", False),

    "in": ("in", False),
    "not_in": ("in", True),

    # NULL handled separately
    "is_null": ("isnull", False),
    "is_not_null": ("isnull", True),
}

DATE_FORMATS = ("%d %b %Y", "%d %B %Y", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d")  

TOKEN_REGEX = re.compile(r"\bNOT\b|\bAND\b|\bOR\b|\(|\)|\d+")

# Utilities for model name resolution
def resolve_model_from_param(model_param: str):
    if not model_param:
        raise LookupError("No model parameter provided")

    # If fully qualified app.model provided
    if "." in model_param:
        app_label, model_name = model_param.split(".", 1)
        return get_model_cached(app_label, model_name)

    # If simple name, check user model first
    UserModel = get_user_model()
    if model_param.lower() == UserModel.__name__.lower():
        return UserModel

    # Default: attempt CRM app
    return get_model_cached("crm", model_param)

# AJAX: Get all CRM models
def get_all_models(request):
    models = apps.get_app_config('crm').get_models()
    model_names = sorted([m.__name__ for m in models])
    return JsonResponse({"models": model_names})


# AJAX: Get fields of selected model
def get_model_fields(request):
    model_param = request.GET.get("model")
    model = resolve_model_from_param(model_param) 
    fields = []

    for f in model._meta.get_fields():

        # Skip reverse relations (auto_created = True)
        if f.auto_created:
            continue

        # Determine field type
        internal_type = f.get_internal_type()

        # CHECK: Is this a FK?
        is_forward_fk = getattr(f, "many_to_one", False) and f.related_model is not None

        # CHECK: Is this a forward ManyToMany?
        is_forward_m2m = getattr(f, "many_to_many", False) and not f.auto_created

        # For both FK and M2M we must return related_model info
        related_model_simple = None
        related_model_label = None

        if is_forward_fk or is_forward_m2m:
            related = f.related_model
            related_model_simple = related.__name__
            related_model_label = f"{related._meta.app_label}.{related.__name__}"
            
        #NEW: Handle choices
        choices = None
        if hasattr(f, "choices") and f.choices:
            choices = [{"value": c[0], "label": c[1]} for c in f.choices]

        # Add field metadata
        fields.append({
            "name": f.name,
            "label": getattr(f, "verbose_name", f.name).replace("_", " ").title(),
            "type": internal_type,
            "related_model": related_model_simple,      
            "related_model_label": related_model_label,  
            "choices": choices,
        })

    return JsonResponse({"fields": fields})


# AJAX: Get FK dropdown values (limited + searchable)
def get_fk_values(request):
    model_param = request.GET.get("model")
    q = request.GET.get("q", "").strip()
    limit = int(request.GET.get("limit", 100))

    model = resolve_model_from_param(model_param)

    qs = model.objects.all()

    # --- Determine searchable fields ---
    candidate_names = ["name", "full_name", "username", "email", "title"]
    concrete_fields = get_concrete_field_names(model)

    search_fields = [n for n in candidate_names if n in concrete_fields]

    if not search_fields:
        # fallback to first CharField/TextField
        for fld in model._meta.get_fields():
            if getattr(fld, "concrete", False):
                if fld.get_internal_type() in ("CharField", "TextField", "EmailField"):
                    search_fields.append(fld.name)
                    break

    # --- Filtering ---
    if q and search_fields:
        q_obj = Q()
        for name in search_fields:
            q_obj |= Q(**{f"{name}__icontains": q})
        qs = qs.filter(q_obj)

    # --- FAST capped count ---
    fast_count = qs.values("pk")[:200].count()
    total_available = fast_count

    # --- Limit actual results ---
    qs = qs.only(*search_fields, model._meta.pk.name)[:limit]

    # --- Build results ---
    results = []
    for obj in qs:
        label = None
        for cand in ("name", "full_name", "username", "email", "title"):
            if hasattr(obj, cand):
                val = getattr(obj, cand)
                if val:
                    label = val
                    break
        if label is None:
            label = str(obj)
        results.append({"id": obj.pk, "label": label})

    return JsonResponse({"results": results, "total": total_available})


# Filter building helpers (your original logic, optimized)
def normalize_date_only(value):
    if not value:
        return value

    # strip any time part following a comma (you had this behavior earlier)
    value = value.split(",")[0].strip()

    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except Exception:
            continue
    return value


def clean_value(value):
    """
    Normalize UI garbage → None
    """
    if value is None:
        return None

    value = str(value).strip()

    if value in {"", "“”", '""', "''"}:
        return None

    return value


def parse_in_values(value, field_type):
    values = [v.strip() for v in value.split(",") if v.strip()]

    # Type casting
    if field_type in ("IntegerField", "BigIntegerField", "AutoField"):
        return [int(v) for v in values if v.isdigit()]

    return values


def build_condition(filter_obj):
    from datetime import datetime, timedelta, time
    field = filter_obj.field_name
    op = filter_obj.operator
    value = clean_value(filter_obj.value)

    model = get_model_cached("crm", filter_obj.list_view.object_name)
    field_obj = get_field_cached(model, field)
    field_type = field_obj.get_internal_type()

    is_date = field_type in ("DateField", "DateTimeField")
    is_fk = field_type == "ForeignKey"

    today = now().date()
    # NULL OPERATORS (works for FK also)
    if op == "is_null":
        if field_type in ("CharField", "TextField"):
            return Q(**{f"{field}__isnull": True}) | Q(**{field: ""})
        return Q(**{f"{field}__isnull": True})

    if op == "is_not_null":
        if field_type in ("CharField", "TextField"):
            return Q(**{f"{field}__isnull": False}) & ~Q(**{field: ""})
        return Q(**{f"{field}__isnull": False})

   
    if is_date and op in {
        "today", "yesterday", "tomorrow",
        "7_days", "30_days",
        "this_month", "last_month"
    }:

        if op == "today":
            start = end = today

        elif op == "yesterday":
            start = end = today - timedelta(days=1)

        elif op == "tomorrow":
            start = end = today + timedelta(days=1)

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
            first = today.replace(day=1)
            last_month_end = first - timedelta(days=1)
            start = last_month_end.replace(day=1)
            end = last_month_end

        # DateTimeField → full-day range
        if field_type == "DateTimeField":
            start_dt = make_aware(datetime.combine(start, time.min))
            end_dt = make_aware(datetime.combine(end, time.max))
            return Q(**{f"{field}__range": (start_dt, end_dt)})

        return Q(**{f"{field}__range": (start, end)})


    # NO VALUE CASE (skip safely)
    if value is None:
        # Only valid cases already handled above
        return Q()


    # DATE NORMALIZATION
    if is_date:
        try:
            value = normalize_date_only(value)

            # ✅ HARD FIX: ensure it's a date object
            if isinstance(value, str):
                value = datetime.strptime(value, "%Y-%m-%d").date()

            if not isinstance(value, date):
                return Q()

        except Exception:
            return Q()

        # 🔥 DateTimeField comparison fix
        if field_type == "DateTimeField" and op in ["lt", "lte", "gt", "gte"]:
            if op == "lt":
                # strictly before the day starts
                value = make_aware(datetime.combine(value, time.min))

            elif op == "lte":
                # include entire day
                value = make_aware(datetime.combine(value, time.max))

            elif op == "gt":
                # strictly after the day ends
                value = make_aware(datetime.combine(value, time.max))

            elif op == "gte":
                # include entire day
                value = make_aware(datetime.combine(value, time.min))

    # DATETIME EQUALITY (date-only compare)
    if field_type == "DateTimeField" and op == "eq":
        return Q(**{f"{field}__date": value})

    # LOOKUP
    lookup, negate = OPERATOR_MAP.get(op, ("exact", False))

    # FK handling → always use id
    if is_fk:
        # If no value → treat as NULL check
        if value in (None, "", "None"):
            return Q(**{f"{field}__isnull": True})
        field_lookup = f"{field}__id__{lookup}"
    else:
        field_lookup = f"{field}__{lookup}"

    # IN / NOT IN
    if lookup == "in":
        try:
            values = parse_in_values(value, field_type)

            if is_fk:
                values = [int(v) for v in values]

            if not values:
                return Q()

            q = Q(**{field_lookup: values})
            return ~q if negate else q

        except Exception:
            return Q()

    # NORMAL FILTER
    try:
        q = Q(**{field_lookup: value})
        return ~q if negate else q

    except Exception:
        return Q()


# Logic parser (tokenize -> parse -> AST -> Q)
def tokenize(text):
    return TOKEN_REGEX.findall(text.upper())

def parse_expression(tokens):
    if not tokens:
        raise ValueError("Empty logic")

    def parse_factor(i):
        if i >= len(tokens):
            raise ValueError("Unexpected end of logic")

        token = tokens[i]

        if token == "NOT":
            node, j = parse_factor(i + 1)
            return ("NOT", node), j

        if token == "(":
            node, j = parse_or(i + 1)

            if j >= len(tokens) or tokens[j] != ")":
                raise ValueError("Missing closing parenthesis")

            return node, j + 1

        if token.isdigit():
            return ("NUM", int(token)), i + 1

        raise ValueError(f"Invalid token: {token}")

    def parse_and(i):
        left, i = parse_factor(i)

        while i < len(tokens) and tokens[i] == "AND":
            right, i = parse_factor(i + 1)
            left = ("AND", left, right)

        return left, i

    def parse_or(i):
        left, i = parse_and(i)

        while i < len(tokens) and tokens[i] == "OR":
            right, i = parse_and(i + 1)
            left = ("OR", left, right)

        return left, i

    root, end = parse_or(0)

    if end != len(tokens):
        raise ValueError("Unexpected tokens in logic")

    return root

def ast_to_q(tree, qmap):
    t = tree[0]

    if t == "NUM":
        num = tree[1]

        # ✅ Safe lookup
        q = qmap.get(num)

        if q is None:
            # Option 1: ignore missing filter
            return Q()

            # Option 2 (strict mode):
            # raise ValueError(f"Invalid filter reference: {num}")

        return q

    if t == "NOT":
        return ~ast_to_q(tree[1], qmap)

    if t == "AND":
        left = ast_to_q(tree[1], qmap)
        right = ast_to_q(tree[2], qmap)
        return left & right

    if t == "OR":
        left = ast_to_q(tree[1], qmap)
        right = ast_to_q(tree[2], qmap)
        return left | right

    raise ValueError("Unknown AST node", tree)

# MAIN: apply_filters(list_view, queryset)
def apply_filters(list_view: ListView, queryset):
    filters = list_view.filters.order_by("row_number")

    if not filters:
        return queryset

    qmap = {f.row_number: build_condition(f) for f in filters}

    logic = (list_view.filter_logic or "").strip()

    if not logic:
        logic = " AND ".join(str(f.row_number) for f in filters)

    try:
        tokens = tokenize(logic)

        # ✅ Empty or invalid token protection
        if not tokens:
            raise ValueError("Empty tokens")

        # ✅ Validate referenced filter numbers
        valid_nums = set(qmap.keys())
        used_nums = {int(t) for t in tokens if t.isdigit()}

        if not used_nums.issubset(valid_nums):
            raise ValueError(f"Invalid filter reference: {used_nums - valid_nums}")

        ast = parse_expression(tokens)
        final_q = ast_to_q(ast, qmap)

    except Exception as e:
        print("⚠️ FILTER LOGIC ERROR:", logic, "|", e)

        # ✅ SAFE FALLBACK (AND all filters)
        final_q = Q()
        for q in qmap.values():
            final_q &= q

    return queryset.filter(final_q)

# Views: home / editor / results / delete
@login_required
def listview_home(request, model_name):
    user = request.user

    views = ListView.objects.filter(
        object_name=model_name
    ).filter(
        # visibility rules
        Q(visibility="public") |
        Q(visibility="private", created_by=user) |
        Q(visibility="groups", created_by=user, visible_groups__in=user.groups.all())
    ).distinct()

    return render(request, "listviews/listview_list.html", {
        "views": views,
        "model_name": model_name,
    })

@login_required
def listview_editor(request, pk=None, model_name=None):
    lv = get_object_or_404(ListView, pk=pk) if pk else None
    
     # ✅ CREATE permission check
    if not lv:
        if not request.user.has_perm("crm.add_listview"):
            return HttpResponseForbidden("<h2>You do not have permission to create a list view.</h2>")

    # ✅ EDIT permission check
    if lv:
        if not request.user.has_perm("crm.change_listview"):
            messages.error(request, "You do not have permission to edit this list view.")
            return redirect(
                f"{reverse('listview_results', kwargs={'model_name': lv.object_name.lower()})}?filter={lv.pk}"
            )

    # Prevent editing the default ListView
    if lv and lv.is_default:
        if not (request.user.is_superuser or request.user.has_perm("crm.can_edit_default_list_views")):
            messages.error(request, "You do not have permission to edit the default list view.")
            return redirect(
                f"{reverse('listview_results', kwargs={'model_name': lv.object_name.lower()})}?filter={lv.pk}"
            )


    available_fields = []
    model = None

    # CASE 1: Editing existing ListView → use lv.object_name
    if lv and lv.object_name:
        model = get_model_cached("crm", lv.object_name)

    # CASE 2: Creating new ListView with model_name passed in URL
    elif model_name:
        lv = ListView()  # temporary instance
        lv.object_name = model_name
        model = get_model_cached("crm", model_name)

    # Load field list if model is known
    if model:
        for f in model._meta.get_fields():
            if f.auto_created:
                continue
            

            is_forward_fk = getattr(f, "many_to_one", False) and getattr(f, "related_model", None) is not None

            if not getattr(f, "concrete", False) and not is_forward_fk:
                continue

            label = getattr(f, "verbose_name", f.name).replace("_", " ").title()
            available_fields.append((f.name, label))
    selected_fields = []

    if lv.pk:
        for f in lv.fields.all():
            model_field = model._meta.get_field(f.field_name)
            selected_fields.append({
                "name": f.field_name,
                "label": model_field.verbose_name.title()
            })


    if request.method == "POST":
        # extra safety: block edit even if POST manually sent
        if lv and lv.is_default:
            if not (request.user.is_superuser or request.user.has_perm("crm.can_edit_default_list_views")):
                messages.error(request, "You do not have permission to edit the default list view.")
                return redirect(
                    f"{reverse('listview_results', kwargs={'model_name': lv.object_name.lower()})}?filter={lv.pk}"
                )

        if pk is None:
            lv = ListView(created_by=request.user)
        else:
           lv.modified_by = request.user 
           
        lv.name = request.POST.get("name") or ""
        lv.object_name = request.POST.get("object_name") or lv.object_name or ""
        lv.filter_logic = request.POST.get("filter_logic") or ""
        lv.visibility = request.POST.get("visibility") or ""
        lv.count = request.POST.get("count")
        lv.save()

        lv.visible_groups.clear()
        if lv.visibility == "groups":
            group_ids = request.POST.getlist("visible_groups[]")
            if group_ids:
                lv.visible_groups.add(*group_ids)

        ListViewField.objects.filter(list_view=lv).delete()
        selected_fields = request.POST.getlist("selected_fields[]")
        for i, fieldname in enumerate(selected_fields):
            if fieldname:
                ListViewField.objects.create(
                    list_view=lv,
                    field_name=fieldname,
                    order=i
                )

        ListViewFilter.objects.filter(list_view=lv).delete()
        from itertools import zip_longest

        filter_fields = request.POST.getlist("filter_field[]")
        filter_ops = request.POST.getlist("filter_operator[]")
        filter_vals = request.POST.getlist("filter_value[]")

        for i, (field, op, val) in enumerate(zip_longest(filter_fields, filter_ops, filter_vals, fillvalue=None)):
            if not field:
                continue

            # -------------------------------
            # HANDLE MULTI / SINGLE VALUE
            # -------------------------------
            if isinstance(val, list):
                # Multi-select (in / not_in)
                val = [v.strip() for v in val if v and str(v).strip()]

                if not val:
                    val = None
                else:
                    val = ",".join(val)   # store as CSV

            else:
                val = (val or "").strip()

                if val in {"", "“”", '""', "''"}:
                    val = None

            # FK empty → convert to is_null
            model = get_model_cached("crm", lv.object_name)
            field_obj = get_field_cached(model, field)

            if field_obj.get_internal_type() == "ForeignKey":
                if not val:
                    op = "is_null"
                elif op in ["in", "not_in"]:
                    # ensure only valid IDs stored
                    val = ",".join([v for v in val.split(",") if v.isdigit()])

            ListViewFilter.objects.create(
                list_view=lv,
                row_number=i + 1,
                field_name=field,
                operator=op,
                value=val
            )

        messages.success(request, "List view saved successfully.")
        return redirect(
            f"{reverse('listview_results', kwargs={'model_name': lv.object_name.lower()})}?filter={lv.pk}"
        )

    filters = list(lv.filters.all()) if lv.pk else [ListViewFilter(row_number=1)]

    return render(request, "listviews/editor.html", {
        "lv": lv,
        "available_fields": available_fields,
        "operators": dict(OPERATORS),
        "selected_fields": selected_fields,
        "filters": filters,
        "groups": Group.objects.all(),
        "model_name": model_name or (lv.object_name if lv else None),
    })


@login_required
def delete_listview(request, pk):
    lv = get_object_or_404(ListView, pk=pk)
    model_name = lv.object_name

    # DELETE permission check
    if not request.user.has_perm("crm.delete_listview"):
        messages.error(request, "You do not have permission to delete this list view.")
        return redirect(
            f"{reverse('listview_results', kwargs={'model_name': model_name.lower()})}?filter={pk}"
        )

    # Prevent deleting default
    if lv.is_default:
        messages.error(request, "The default list view cannot be deleted.")
        return redirect(
            f"{reverse('listview_results', kwargs={'model_name': model_name.lower()})}?filter={pk}"
        )


    if request.method == "POST":

        # Re-check permission (important)
        if not request.user.has_perm("crm.delete_listview"):
            messages.error(request, "Permission denied.")
            return redirect(
                f"{reverse('listview_results', kwargs={'model_name': model_name.lower()})}?filter={pk}"
            )

        lv.delete()

        default_lv = get_default_listview(model_name, request.user)

        if default_lv:
            return redirect(
                f"{reverse('listview_results', kwargs={'model_name': model_name.lower()})}?filter={default_lv.pk}"
            )

        fallback_lv = (
            ListView.objects
            .filter(object_name=model_name)
            .order_by("id")
            .first()
        )

        if fallback_lv:
            return redirect(
                f"{reverse('listview_results', kwargs={'model_name': model_name.lower()})}?filter={fallback_lv.pk}"
            )

        return redirect("listview_home", model_name=model_name.lower())

    return render(request, "listviews/confirm_delete.html", {"lv": lv})

def listview_visibility_filter(user):
    return (
        Q(visibility="public") |
        Q(visibility="private", created_by=user) |
        Q(visibility="groups") & (
            Q(created_by=user) |
            Q(visible_groups__in=user.groups.all())
        )
    )

def get_available_listviews(model_name, user):
    return ListView.objects.filter(
        object_name=model_name
    ).filter(
        listview_visibility_filter(user)
    ).distinct()

def get_default_listview(model_name, user):
    return get_available_listviews(model_name, user).filter(is_default=True).first()


def get_listview_if_allowed(pk, user):
    return ListView.objects.filter(
        pk=pk
    ).filter(
        listview_visibility_filter(user)
    ).first()


@login_required
def listview_results(request, model_name):
    user = request.user
    pk = request.GET.get("filter")

    MODEL_MAP = {
        "lead": "Lead",
        "bank": "Bank",
        "loanapplication": "LoanApplication",
        "loanproduct": "LoanProduct",
        "bankfeedback": "BankFeedback",
        "candidateonboarding": "CandidateOnboarding",
        "contact": "Contact",
        "productcategory": "ProductCategory",
        "product": "Product",
        "branch":"Branch"
    }

    model_key = (model_name or "").lower()
    model_name_mapped = MODEL_MAP.get(model_key)

    if not model_name_mapped:
        return HttpResponseBadRequest(f"Invalid model name: {model_key}")

    model_url = model_key

    # -----------------------------------------------------------------
    # FETCH OR CREATE LISTVIEW IF PK IS NOT PROVIDED
    # -----------------------------------------------------------------
    if not pk:
        # 1. Attempt to get an existing default or configured fallback view
        default_lv = get_default_listview(
            model_name_mapped, user
        ) or get_available_listviews(model_name_mapped, user).first()

        # 2. ✅ FIX: If nothing exists in the DB, invoke the auto-generator
        if not default_lv:
            default_lv = get_or_create_default_listview(
                model_name_mapped, user=user
            )

        # 3. Last line of defense safety check
        if not default_lv:
            return HttpResponseBadRequest(
                f"No ListView available or could be created for {model_name_mapped}."
            )

        # IMPORTANT: Do NOT redirect if exporting to Excel
        if request.GET.get("export") != "excel":
            url = reverse("listview_results", kwargs={"model_name": model_url})
            return redirect(f"{url}?filter={default_lv.pk}")

        lv = default_lv
    else:
        try:
            pk = int(pk)
        except ValueError:
            return HttpResponseBadRequest("Invalid ID")

        lv = get_listview_if_allowed(pk, user)
        if not lv:
            return HttpResponseForbidden(
                "You do not have access to this ListView."
            )

    # -----------------------------------------------------------------
    # MODEL & PERMISSION CHECKS
    # -----------------------------------------------------------------
    model = get_model_cached("crm", lv.object_name)
    has_view_access = f"{model._meta.app_label}.view_{model.__name__.lower()}"

    if model_name_mapped.lower() == "candidateonboarding":
        if not (
            user.has_perm(has_view_access)
            and user.has_perm("crm.can_access_hr_module")
        ):
            return HttpResponseForbidden(
                "You do not have permission to view these records."
            )
    else:
        if not user.has_perm(has_view_access):
            return HttpResponseForbidden(
                "You do not have permission to view these records."
            )

    # -----------------------------------------------------------------
    # BASE QUERYSET & FIELD CONFIGURATION
    # -----------------------------------------------------------------
    queryset = apply_filters(lv, get_visible_queryset(model, user))

    fields = []
    visible_field_names = ["id"]

    for field_obj in lv.fields.all():
        field_name = field_obj.field_name

        if not is_field_visible(user, model, field_name):
            continue

        meta_field = get_field_cached(model, field_name)

        fields.append(
            {
                "name": field_name,
                "label": meta_field.verbose_name.title(),
            }
        )
        visible_field_names.append(field_name)

    valid_field_names = set(visible_field_names) | {"pk"}

    # -----------------------------------------------------------------
    # EXPORT HOOK
    # -----------------------------------------------------------------
    if request.GET.get("export") == "excel":
        select_mode = request.GET.get("select_mode", "page")
        excluded_ids = request.GET.get("excluded_ids", "")

        if select_mode == "all":
            qs = queryset
            if excluded_ids:
                qs = qs.exclude(pk__in=excluded_ids.split(","))
        else:
            ids = request.GET.getlist("selected_ids")
            ids = [int(i) for i in ids if i.isdigit()]
            qs = queryset.filter(pk__in=ids)

        return export_queryset_to_excel(
            request=request,
            queryset=qs,
            permission_codename="crm.can_export_data",
            field_names=["id"] + [f["name"] for f in fields],
        )

    # -----------------------------------------------------------------
    # GLOBAL SEARCH HANDLING
    # -----------------------------------------------------------------
    search_query = request.GET.get("q", "").strip()

    if model.__name__ == "Lead":
        SEARCH_FIELDS = [
            "id",
            "name",
            "mobile_number",
            "application_no",
            "lender_name__name",
            "assigned_to__username",
            "tele_sales_executive__username",
            "team_lead__username",
        ]

        STATUS_LABEL_MAP = {
            label.lower(): value for value, label in LEAD_STATUS_CHOICES
        }
        LEAD_SOURCE_LABEL_MAP = {
            label.lower(): value for value, label in LEAD_TYPE_CHOICES
        }

        if search_query:
            search_lower = search_query.lower()
            q_final = Q()

            for field in SEARCH_FIELDS:
                q_final |= Q(**{f"{field}__icontains": search_query})

            for label, value in STATUS_LABEL_MAP.items():
                if search_lower == label or search_lower in label:
                    q_final |= Q(status=value)

            for label, value in LEAD_SOURCE_LABEL_MAP.items():
                if search_lower == label or search_lower in label:
                    q_final |= Q(lead_source=value)

            queryset = queryset.filter(q_final)

    if search_query and model.__name__ != "Lead":
        terms = search_query.split()
        q_final = Q()

        for term in terms:
            q_term = Q()
            is_int = term.isdigit()

            for field_name in visible_field_names:
                meta_field = get_field_cached(model, field_name)
                field_type = meta_field.get_internal_type()

                if field_type in (
                    "CharField",
                    "TextField",
                    "EmailField",
                    "SlugField",
                ):
                    q_term |= Q(**{f"{field_name}__icontains": term})

                elif field_type in (
                    "IntegerField",
                    "BigIntegerField",
                    "PositiveIntegerField",
                    "PositiveSmallIntegerField",
                    "AutoField",
                    "BigAutoField",
                ):
                    if is_int:
                        q_term |= Q(**{field_name: int(term)})

                elif field_type in ("BooleanField", "NullBooleanField"):
                    if term.lower() in ("true", "yes", "1"):
                        q_term |= Q(**{field_name: True})
                    elif term.lower() in ("false", "no", "0"):
                        q_term |= Q(**{field_name: False})

                elif field_type in ("DateField", "DateTimeField"):
                    q_term |= Q(**{f"{field_name}__icontains": term})

                elif meta_field.is_relation and meta_field.many_to_one:
                    if is_int:
                        q_term |= Q(**{f"{field_name}_id": int(term)})

            q_final &= q_term

        queryset = queryset.filter(q_final)

    # -----------------------------------------------------------------
    # SORTING & QUERY PERFORMANCE HOOKS
    # -----------------------------------------------------------------
    sort_field = request.GET.get("sort", "id")
    sort_dir = request.GET.get("dir", "desc")

    if sort_field in valid_field_names:
        order_by = f"-{sort_field}" if sort_dir == "desc" else sort_field
    else:
        order_by = "-id"

    queryset = queryset.order_by(order_by)

    if model.__name__ == "Lead":
        queryset = queryset.select_related(
            "assigned_to",
            "tele_sales_executive",
            "sm",
            "team_lead",
            "business_manager",
            "business_head",
            "bank",
            "lender_name",
        ).defer(
            "description",
            "existing_loan_details",
            "existing_cc_details",
            "reference_details_friend",
            "reference_details_relative",
            "nominee_details",
            "final_remarks",
        )

    # -----------------------------------------------------------------
    # LIGHTWEIGHT PAGINATION SYSTEM
    # -----------------------------------------------------------------
    page_size = lv.count or 10
    page = int(request.GET.get("page", 1))

    total_count = queryset.values("pk").count()

    start = (page - 1) * page_size
    end = start + page_size

    rows = list(queryset[start:end])
    has_next = end < total_count

    page_obj = SimpleNamespace(
        object_list=rows,
        number=page,
        has_next=lambda: has_next,
        has_previous=lambda: page > 1,
        next_page_number=lambda: page + 1,
        previous_page_number=lambda: max(page - 1, 1),
        start_index=lambda: start + 1 if rows else 0,
        end_index=lambda: start + len(rows),
        paginator=SimpleNamespace(
            count=total_count,
            num_pages=ceil(total_count / page_size),
            page_range=range(1, ceil(total_count / page_size) + 1),
        ),
    )

    # -----------------------------------------------------------------
    # DATA RENDERING PIPELINE
    # -----------------------------------------------------------------
    rendered_rows = []
    for obj in page_obj.object_list:
        row = {"pk": obj.pk}
        for f in fields:
            _, value = get_rendered_field(model, obj, f["name"])
            row[f["name"]] = value
        rendered_rows.append(row)

    return render(
        request,
        "listviews/results.html",
        {
            "lv": lv,
            "rows": rendered_rows,
            "fields": fields,
            "page_obj": page_obj,
            "available_listviews": get_available_listviews(
                lv.object_name, user
            ),
            "current_sort": sort_field,
            "current_dir": sort_dir,
            "model_name": model_name_mapped,
            "model_url": model_url,
        },
    )


# For exporting to excel by Ashutosh
ILLEGAL_CHARACTERS_RE = re.compile(r'[\x00-\x08\x0B-\x0C\x0E-\x1F]')
def clean_excel_value(value):
    if isinstance(value, str):
        return ILLEGAL_CHARACTERS_RE.sub('', value)
    return value

def export_queryset_to_excel(
    request,
    queryset,
    permission_codename,
    field_names
):

    # PERMISSION
    if not request.user.has_perm(permission_codename):
        raise PermissionDenied(
            "You do not have permission to export data."
        )

    model = queryset.model

    fields = [
        get_field_cached(model, name)
        for name in field_names
    ]

    # RESPONSE
    filename = (
        f"{model.__name__.lower()}_export_"
        f"{datetime.datetime.now().strftime('%d-%m-%Y_%H-%M-%S')}.csv"
    )

    response = HttpResponse(
        content_type="text/csv"
    )

    response["Content-Disposition"] = (
        f'attachment; filename="{filename}"'
    )

    writer = csv.writer(response)

    # HEADERS
    headers = [
        field.verbose_name.title()
        for field in fields
    ]

    writer.writerow(headers)

    # FK MAPS
    fk_maps = {}

    for field in fields:

        if field.is_relation and field.many_to_one:

            related_model = field.related_model

            # Detect display field
            display_field = None

            for candidate in [
                "name",
                "full_name",
                "username",
                "title",
                "email",
            ]:
                try:
                    related_model._meta.get_field(candidate)
                    display_field = candidate
                    break
                except Exception:
                    pass

            if not display_field:
                display_field = "id"

            fk_maps[field.name] = dict(
                related_model.objects.values_list(
                    "id",
                    display_field
                )
            )

    # CHOICE MAPS
    choice_maps = {}
    for field in fields:

        if field.choices:
            choice_maps[field.name] = dict(
                field.choices
            )
    # FAST QUERY
    export_field_names = [
        field.name
        for field in fields
    ]
    queryset = queryset.order_by("id")

    # STREAM ROWS
    for row_data in queryset.values(
        *export_field_names
    ).iterator(chunk_size=10000):
        cleaned_row = []

        for field in fields:

            value = row_data.get(field.name)
            # FK LABEL
            if field.name in fk_maps:

                value = fk_maps[field.name].get(
                    value,
                    value
                )

            # CHOICE LABEL
            elif field.name in choice_maps:

                value = choice_maps[field.name].get(
                    value,
                    value
                )
            # DATETIME
            elif isinstance(value, datetime.datetime):

                if is_aware(value):
                    value = value.astimezone(None).replace(tzinfo=None)

                value = value.strftime("%d-%m-%Y %H:%M:%S")


           
            # DATE
            elif isinstance(value, datetime.date):

                value = value.strftime(
                    "%d-%m-%Y"
                )

            
            # NONE SAFETY
            if value is None:
                value = ""

            cleaned_row.append(value)

        writer.writerow(cleaned_row)

    return response

# def export_queryset_to_excel(request, queryset, permission_codename, field_names):

#     if not request.user.has_perm(permission_codename):
#         raise PermissionDenied("You do not have permission to export data.")

#     model = queryset.model

#     fields = [get_field_cached(model, name) for name in field_names]

#     headers = [field.verbose_name.title() for field in fields]

#     wb = Workbook(write_only=True)

#     ws = wb.create_sheet(
#         title=model._meta.verbose_name_plural.title()
#     )

#     ws.append(headers)

#   
#     # BUILD FK MAPS
#   
#     fk_maps = {}

#     for field in fields:

#         if field.is_relation and field.many_to_one:

#             related_model = field.related_model

#             fk_maps[field.name] = dict(
#                 related_model.objects.values_list(
#                     "id",
#                     "name" if hasattr(related_model, "name")
#                     else "username"
#                     if hasattr(related_model, "username")
#                     else "id"
#                 )
#             )

#   
#     # CHOICE MAPS
#   
#     choice_maps = {}

#     for field in fields:

#         if field.choices:
#             choice_maps[field.name] = dict(field.choices)

#   
#     # FAST EXPORT
#   
#     export_field_names = [f.name for f in fields]

#     queryset = queryset.order_by("id")

#     for row_data in queryset.values(
#         *export_field_names
#     ).iterator(chunk_size=5000):

#         cleaned_row = []

#         for field in fields:

#             value = row_data.get(field.name)

#             # -------------------------
#             # FK LABEL
#             # -------------------------
#             if field.name in fk_maps:

#                 value = fk_maps[field.name].get(value, value)

#             # -------------------------
#             # CHOICE LABEL
#             # -------------------------
#             elif field.name in choice_maps:

#                 value = choice_maps[field.name].get(value, value)

#             # -------------------------
#             # DATETIME
#             # -------------------------
#             elif isinstance(value, datetime.datetime):

#                 if is_aware(value):
#                     value = value.astimezone(None).replace(tzinfo=None)

#                 value = value.strftime("%d-%m-%Y %H:%M:%S")

#             # -------------------------
#             # DATE
#             # -------------------------
#             elif isinstance(value, datetime.date):

#                 value = value.strftime("%d-%m-%Y")

#             # -------------------------
#             # CLEANUP
#             # -------------------------
#             value = clean_excel_value(value)

#             cleaned_row.append(value)

#         ws.append(cleaned_row)

#     buffer = BytesIO()

#     wb.save(buffer)

#     buffer.seek(0)

#     filename = (
#         f"{model.__name__.lower()}_export_"
#         f"{datetime.datetime.now().strftime('%d-%m-%Y_%H-%M-%S')}.xlsx"
#     )

#     response = HttpResponse(
#         buffer,
#         content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
#     )

#     response["Content-Disposition"] = (
#         f'attachment; filename="{filename}"'
#     )

#     return response

from django.views.decorators.http import require_GET
# TO check name uniqueness
@login_required
@require_GET
def check_listview_name(request):
    print("✅ VIEW HIT")   # <-- ADD THIS

    try:
        name = request.GET.get("name", "").strip()
        obj_id = request.GET.get("id", "").strip()

        if not name:
            return JsonResponse({"exists": False})

        qs = ListView.objects.filter(name__iexact=name)

        if obj_id:
            try:
                qs = qs.exclude(id=int(obj_id))
            except:
                pass

        return JsonResponse({"exists": qs.exists()})

    except Exception as e:
        print("ERROR:", e)
        return JsonResponse({"exists": False})