from __future__ import annotations
from datetime import datetime
from urllib import request
from django.apps import apps
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.views.generic import DetailView, DeleteView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView
from django.utils.text import slugify
from crm.choices import CHANNEL_CHOICES
from crm.models import Bank, Lead, UserProfile
from reports.filters import build_q
from reports.query_filters import _normalize_filter_dict
from reports.utils import build_breadcrumbs
from .models import Report, User
from .spec import ReportSpec
from .engine import ReportEngine
from .forms import (
    FilterForm,
    SelectFieldsForm,
    GroupMeasureForm,
    ReportEditForm,
)
from django.db import models
import csv
from crm.listview_views import tokenize, parse_expression, ast_to_q
# MTD Report View by Ashutosh
from django.db.models import Sum, Count, Case, When, F, IntegerField, IntegerField
from openpyxl.utils import get_column_letter
import openpyxl
from crm.utils import get_visible_queryset
from django.db.models import Q
from django.contrib.auth import get_user_model
import uuid
from django.views.decorators.http import require_GET
from django.utils import timezone
from datetime import datetime, date
from django.db import connection
from datetime import datetime, timedelta


WIZ_SESSION_KEY = "report_wizard"


class ReportListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Report
    template_name = "reports/list.html"
    paginate_by = 10
    permission_required = "reports.view_report"
    raise_exception = False

    def handle_no_permission(self):
        return HttpResponse(
            "<h3>❌ You don't have permission to View report.</h3>",
            status=403
        )

    def get_queryset(self):
        qs = super().get_queryset().filter(is_active=True)

        user = self.request.user

        allowed_reports = []

        for report in qs:
            try:
                spec = ReportSpec.from_dict(report.spec)

                app_label, model_name = spec.model.split(".")

                perm = f"{app_label}.view_{model_name.lower()}"

                if user.has_perm(perm):
                    allowed_reports.append(report.id)

            except Exception:
                continue  # skip broken specs safely

        return qs.filter(id__in=allowed_reports)


def _json_safe_measures(val):
    safe = []
    if not val:
        return safe
    for m in val:
        if isinstance(m, dict):
            safe.append({
                "fn": m.get("fn"),
                "field": m.get("field"),
                "label": m.get("label"),
            })
        else:
            fn = getattr(m, "fn", None)
            field = getattr(m, "field", None)
            label = getattr(m, "label", None)
            if not label:
                label = "Count" if (fn or "").lower() == "count" else f"{(fn or '').upper()} {field or ''}".strip()
            safe.append({"fn": fn, "field": field, "label": label})
    return safe


def _json_safe_groups(val):
    """Coerce any group-like thing to {'field': <name>} dicts."""
    safe = []
    if not val:
        return safe
    for g in val:
        if hasattr(g, "field"):  # GroupSpec or similar object
            safe.append({"field": getattr(g, "field")})
        elif isinstance(g, dict):
            fld = g.get("field") if "field" in g else g.get("name") or g.get("value")
            if fld:
                safe.append({"field": fld})
        else:  # string
            safe.append({"field": str(g)})
    return safe


def _sanitize_wizard_session(request):
    data = request.session.get(WIZ_SESSION_KEY)
    if not data:
        return {}
    changed = False
    if "rep_measures" in data:
        safe = _json_safe_measures(data.get("rep_measures"))
        if safe != data.get("rep_measures"):
            data["rep_measures"] = safe
            changed = True
    if "rep_row_groups" in data:
        safe = _json_safe_groups(data.get("rep_row_groups"))
        if safe != data.get("rep_row_groups"):
            data["rep_row_groups"] = safe
            changed = True
    if "rep_col_groups" in data:
        safe = _json_safe_groups(data.get("rep_col_groups"))
        if safe != data.get("rep_col_groups"):
            data["rep_col_groups"] = safe
            changed = True
    if changed:
        request.session[WIZ_SESSION_KEY] = data
        request.session.modified = True
    return data


def _map_names_to_choice_values(choices, stored_names):
    """
    Map stored group names (strings) to actual form choice values.
    Tries: direct value match, direct label match, tail-match on '__' or '.'.
    """
    if not stored_names:
        return []
    want = []
    values = [str(v) for v, _ in choices]

    def candidates_for(name: str):
        if not name:
            return []
        name = str(name)
        tail = name.split(".")[-1]
        tail = tail.split("__")[-1]
        cands = []
        if name in values:
            cands.append(name)
        for v in values:
            if v == tail or v.endswith("__" + tail):
                cands.append(v)
        return cands

    for item in stored_names:
        if hasattr(item, "field"):  # GroupSpec object
            key = str(getattr(item, "field"))
        elif isinstance(item, dict):
            key = str(item.get("field") or item.get("name") or item.get("value") or "")
        else:
            key = str(item)
        matched = candidates_for(key)
        if matched:
            want.append(matched[0])
    # dedupe preserve order
    seen, deduped = set(), []
    for v in want:
        if v not in seen:
            deduped.append(v)
            seen.add(v)
    return deduped

def ensure_filter_ids(filters):
    updated = False
    out = []
    for f in (filters or []):
        if not isinstance(f, dict):
            continue
        if "id" not in f or not f.get("id"):
            f["id"] = str(uuid.uuid4())
            updated = True
        out.append({
            "id": f.get("id"),
            "field": f.get("field"),
            "op": f.get("op") or "eq",
            "value": f.get("value"),
        })
    return out, updated

@login_required
def report_wizard(request, slug: str | None = None):
    """
    Unified wizard for New + Edit
    """
    editing = bool(slug)
    if editing:
        if not request.user.has_perm("reports.change_report"):
            return HttpResponse("<h2>❌ You do not have permission to edit reports. </h2>", status=403)
    else:
        if not request.user.has_perm("reports.add_report"):
            return HttpResponse("<h2>❌ You do not have permission to add reports. </h2>", status=403)
    rep = None
    if editing:
        rep = get_object_or_404(Report, slug=slug, is_active=True)
        spec = ReportSpec.from_dict(rep.spec or {})
    else:
        spec = None

    session = _sanitize_wizard_session(request) or {}
    step = request.GET.get("step", "basic")
    # Build breadcrumbs
    breadcrumbs = build_breadcrumbs(editing, slug, step, rep, session.get("rep_view"))


    # STEP 1: BASIC
    if step == "basic":

        initial = {
            "name": rep.name if editing else session.get("rep_name"),
            "description": rep.description if editing else session.get("rep_description"),
            "model": rep.base_model if editing else session.get("rep_model"),
            "view": rep.view_type if editing else session.get("rep_view"),
        }

        from django import forms
        from .forms import SelectObjectForm, SelectTypeForm

        class BasicForm(forms.Form):
            name = forms.CharField(widget=forms.TextInput(attrs={"class": "form-control"}))
            model = SelectObjectForm().fields["model"]
            view = SelectTypeForm().fields["view"]
            description = forms.CharField(
                required=False,
                widget=forms.Textarea(attrs={"class": "form-control", "rows": 3})
            )

        form = BasicForm(request.POST or None, initial=initial)

        if request.method == "POST" and form.is_valid():
            session["rep_name"] = form.cleaned_data["name"]
            session["rep_description"] = form.cleaned_data["description"]
            session["rep_model"] = form.cleaned_data["model"]
            session["rep_view"] = form.cleaned_data["view"]
            
            session["edit_slug"] = slug if editing else None
            request.session[WIZ_SESSION_KEY] = session
            request.session.modified = True

            return redirect(f"{request.path}?step=design")

        return render(request, "reports/wizard_basic.html", {"form": form, "breadcrumbs": breadcrumbs})

    # COMMON
    model_label = session.get("rep_model") or (rep.base_model if editing else None)
    view_type = session.get("rep_view") or (rep.view_type if editing else "summary")

    if not model_label:
        return redirect(f"{request.path}?step=basic")

    # Step 3: design
    if step == "design":
        if view_type == "tabular":
            initial_fields = spec.fields if editing else session.get("rep_fields", [])
            form = SelectFieldsForm(model_label, request.POST or None, initial={"fields": initial_fields})
            if request.method == "POST" and form.is_valid():
                session["rep_fields"] = form.cleaned_data["fields"]
                request.session[WIZ_SESSION_KEY] = session
                request.session.modified = True
                return redirect(f"{request.path}?step=filters")
            return render(request, "reports/wizard_tabular.html", {"form": form,"breadcrumbs": breadcrumbs, "model": model_label})

        # -------- summary / matrix --------
        selected_row_groups, selected_col_groups = [], []
        dbg_rg_src, dbg_cg_src = [], []           # DEBUG: raw stored groups
        dbg_row_choices, dbg_col_choices = [], [] # DEBUG: choices in the form
        dbg_form_field_names = []                 # DEBUG: form field names

        if request.method == "POST":
            form = GroupMeasureForm(model_label, request.POST)
        else:
            # Build a temp form just to read CHOICES and field names
            tmp = GroupMeasureForm(model_label)
            dbg_form_field_names = list(tmp.fields.keys())
            dbg_row_choices = [str(v) for v, _ in tmp.fields["row_groups"].choices]
            if "col_groups" in tmp.fields:
                dbg_col_choices = [str(v) for v, _ in tmp.fields["col_groups"].choices]

            # Pull sources (prefer DB spec on edit; else session)
            rg_src = (spec.row_groups if editing else session.get("rep_row_groups", [])) or []
            cg_src = (spec.col_groups if editing else session.get("rep_col_groups", [])) or []
            dbg_rg_src = rg_src
            dbg_cg_src = cg_src

            # Map stored names/objects -> actual choice values
            selected_row_groups = _map_names_to_choice_values(tmp.fields["row_groups"].choices, rg_src)
            if "col_groups" in tmp.fields:
                selected_col_groups = _map_names_to_choice_values(tmp.fields["col_groups"].choices, cg_src)

            # Measure initial
            if editing and getattr(spec, "measures", None):
                m_fn = spec.measures[0].fn or "count"
                m_field_name = spec.measures[0].field or ""
            elif session.get("rep_measures"):
                m = session["rep_measures"][0]
                m_fn = m.get("fn", "count")
                m_field_name = (m.get("field") or "")
            else:
                m_fn, m_field_name = "count", ""

            # normalize object → field name if needed
            if hasattr(m_field_name, "field"):
                m_field_name = m_field_name.field

            field_choices = tmp.fields["field"].choices
            mv = _map_names_to_choice_values(field_choices, [m_field_name] if m_field_name else [])
            m_field_value = mv[0] if mv else ""

            initial = {
                "row_groups": selected_row_groups,
                "col_groups": selected_col_groups,
                "fn": m_fn,
                "field": m_field_value,
            }
            # Now instantiate the real form with initial, so .value() works in the template
            form = GroupMeasureForm(model_label, initial=initial)

        if request.method == "POST" and form.is_valid():
            session["rep_row_groups"] = [{"field": f} for f in form.cleaned_data["row_groups"]]
            session["rep_col_groups"] = [{"field": f} for f in form.cleaned_data["col_groups"]] if view_type == "matrix" else []
            fn = form.cleaned_data["fn"]
            field = form.cleaned_data.get("field")
            label = (f"{fn.upper()} {field}" if field else "Count")
            session["rep_measures"] = [{"fn": fn, "field": field, "label": label}]
            request.session[WIZ_SESSION_KEY] = session
            request.session.modified = True
            return redirect(f"{request.path}?step=filters")

        return render(
            request,
            "reports/wizard_group.html",
            {
                "form": form,
                "model": model_label,
                "view": view_type,
                # explicit selections (strings)
                "selected_row_groups": [str(v) for v in selected_row_groups],
                "selected_col_groups": [str(v) for v in selected_col_groups],
                # DEBUG context (keep while validating)
                "dbg_rg_src": dbg_rg_src,
                "dbg_cg_src": dbg_cg_src,
                "dbg_row_choices": dbg_row_choices,
                "dbg_col_choices": dbg_col_choices,
                "dbg_form_field_names": dbg_form_field_names,
                "breadcrumbs": breadcrumbs,
            },
        )
    
    
    # STEP: FILTERS (FINAL STEP — SAVE + RUN)
    if step == "filters":

        if not model_label:
            return redirect(f"{request.path}?step=basic")

        session = request.session.get(WIZ_SESSION_KEY, {})

        # MODEL + FIELD CHOICES
        app_label, model_name = model_label.split(".")
        model = apps.get_model(app_label, model_name)

        usable_fields = [
            f for f in model._meta.fields
            if not f.many_to_many and not f.auto_created
        ]

        field_choices = [('', '--- Select Field ---')] + [
            (f.name, f.verbose_name.title()) for f in usable_fields
        ]

        form = FilterForm(field_choices=field_choices, model_label=model_label)

        # LOAD EXISTING DATA
        if editing:
            filters = rep.spec.get("filters", [])
            filter_logic = rep.spec.get("filter_logic", "")
        else:
            filters = session.get("rep_filters", [])
            filter_logic = session.get("rep_filter_logic", "")

        filters = [_normalize_filter_dict(f) for f in filters]

        # DELETE
        delete_id = request.GET.get("delete")
        if delete_id:
            filters = [f for f in filters if str(f.get("id")) != delete_id]

            if editing:
                rep.spec["filters"] = filters
                rep.save()
            else:
                session["rep_filters"] = filters
                request.session[WIZ_SESSION_KEY] = session
                request.session.modified = True

            return redirect(f"{request.path}?step=filters")

        # RESET
        if request.GET.get("reset") == "1":
            if editing:
                rep.spec["filters"] = []
                rep.spec["filter_logic"] = ""
                rep.save()
            else:
                session["rep_filters"] = []
                session["rep_filter_logic"] = ""
                request.session[WIZ_SESSION_KEY] = session
                request.session.modified = True

            return redirect(f"{request.path}?step=filters")

        # FINAL SUBMIT (SAVE + RUN)
        if request.method == "POST":

            # ---- BASIC DATA (from session / DB)
            if editing:
                name = session.get("rep_name") or (rep.name if editing else None)
                description = session.get("rep_description") or (rep.description if editing else "")
            else:
                name = session.get("rep_name")
                description = session.get("rep_description")

            limit = (
                int(request.POST.get("limit"))
                if request.POST.get("limit")
                else (
                    session.get("rep_limit")
                    or (rep.limit if editing else 5000)
                )
            )

            # ---- FILTER INPUT
            fields = request.POST.getlist("field[]")
            conditions = request.POST.getlist("condition[]")
            values = request.POST.getlist("value[]")
            filter_logic = request.POST.get("filter_logic", "").strip()

            new_filters = []

            for i, field in enumerate(fields):

                if not field:
                    continue

                condition = conditions[i] if i < len(conditions) else "eq"
                value = values[i] if i < len(values) else ""

                row_form = FilterForm(
                    {"field": field, "condition": condition, "value": value},
                    field_choices=field_choices,
                    model_label=model_label
                )

                if not row_form.is_valid():
                    temp_filters = [{
                        "field": fields[j],
                        "op": conditions[j] if j < len(conditions) else "eq",
                        "value": values[j] if j < len(values) else "",
                        "row_number": j + 1,
                    } for j in range(len(fields))]

                    return render(request, "reports/wizard_filters.html", {
                        "form": row_form,
                        "filters": temp_filters,
                        "filter_logic": filter_logic,
                        "model_label": model_label,
                        "breadcrumbs": breadcrumbs,
                    })

                new_filters.append({
                    "id": str(uuid.uuid4()),
                    "row_number": i + 1,
                    "field": field,
                    "op": condition or "eq",
                    "value": value or "",
                })

            # ---- DESIGN DATA
            base_spec = rep.spec if editing else {}

            spec_dict = {
                "model": model_label,
                "view": view_type,
                "limit": limit,

                "fields": session.get("rep_fields") 
                        if session.get("rep_fields") is not None 
                        else base_spec.get("fields", []),

                "row_groups": session.get("rep_row_groups") 
                            if session.get("rep_row_groups") is not None 
                            else base_spec.get("row_groups", []),

                "col_groups": session.get("rep_col_groups") 
                            if session.get("rep_col_groups") is not None 
                            else base_spec.get("col_groups", []),

                "measures": session.get("rep_measures") 
                            if session.get("rep_measures") is not None 
                            else base_spec.get("measures", []),

                "filters": new_filters,
                "filter_logic": filter_logic,
                "sort": None,
            }

            # ---- SAVE (single point)
            if editing:
                rep.name = name
                rep.description = description
                rep.limit = limit
                rep.base_model = model_label
                rep.view_type = view_type
                rep.spec = spec_dict
                rep.modified_by = request.user

                if not rep.assigned_to:
                    rep.assigned_to = request.user

                rep.save()

            else:
                rep = Report.objects.create(
                    name=name,
                    slug=slugify(name),
                    owner=request.user,
                    base_model=model_label,
                    view_type=view_type,
                    spec=spec_dict,
                    limit=limit,
                    description=description,
                    created_by=request.user,
                    assigned_to=request.user,
                )

            # ---- CLEAR SESSION
            request.session.pop(WIZ_SESSION_KEY, None)

            # ---- RUN REPORT
            return redirect("reports:run", slug=rep.slug)

        
        return render(request, "reports/wizard_filters.html", {
            "form": form,
            "filters": filters,
            "filter_logic": filter_logic,
            "model_label": model_label,
            "breadcrumbs": breadcrumbs,
            "limit": rep.limit if editing else 5000,
        })
            


def build_verbose_spec(report):
    raw = report.spec or {}

    # ===== MODEL RESOLUTION =====
    model = None
    model_label = raw.get("model")

    if model_label:
        try:
            app_label, model_name = model_label.split(".")
            model = apps.get_model(app_label, model_name)
        except Exception:
            model = None

    # ===== FIELD RESOLVER =====
    def get_field_and_model(field_name):
        if not model:
            return None, None

        parts = field_name.split("__")
        current_model = model
        field = None

        try:
            for part in parts:
                field = current_model._meta.get_field(part)

                if hasattr(field, "related_model") and field.related_model:
                    current_model = field.related_model

            return field, current_model
        except Exception:
            return None, None

    # ===== VERBOSE LABEL =====
    def get_verbose(field_name):
        if not model or not field_name:
            return field_name

        parts = field_name.split("__")
        current_model = model
        labels = []

        for part in parts:
            try:
                field = current_model._meta.get_field(part)
                labels.append(field.verbose_name.title())

                if hasattr(field, "related_model") and field.related_model:
                    current_model = field.related_model

            except Exception:
                # 🔥 fallback for non-model fields
                labels.append(part.replace("_", " ").title())

        return " → ".join(labels)

    # ===== NORMALIZE VALUE =====
    def normalize_value(value):
        if isinstance(value, str) and "," in value:
            return [v.strip() for v in value.split(",") if v.strip()]
        return value

    # ===== RESOLVE VALUE (FK + CHOICES) =====
    def resolve_value(field_name, value):
        if value in [None, ""] or not model:
            return value

        value = normalize_value(value)

        field, _ = get_field_and_model(field_name)
        if not field:
            return value

        # FK
        if hasattr(field, "related_model") and field.related_model:
            rel_model = field.related_model

            def display(obj):
                for attr in ["username", "name", "title"]:
                    if hasattr(obj, attr):
                        return getattr(obj, attr)
                return str(obj)

            if isinstance(value, list):
                ids = [int(v) for v in value if str(v).isdigit()]
                return [display(o) for o in rel_model.objects.filter(pk__in=ids)]

            if str(value).isdigit():
                obj = rel_model.objects.filter(pk=int(value)).first()
                return display(obj) if obj else value

            return value

        # CHOICES
        if field.choices:
            choice_map = dict(field.flatchoices)

            if isinstance(value, list):
                return [choice_map.get(v, v) for v in value]

            return choice_map.get(value, value)

        return value

    # ===== FIELD MAPPERS =====
    def map_fields(field_list):
        return [get_verbose(f) for f in field_list if isinstance(f, str)]

    def map_group_fields(group_list):
        labels = []
        for item in group_list:
            field_name = item.get("field") if isinstance(item, dict) else item
            labels.append(get_verbose(field_name))
        return labels

    def map_measures(measure_list):
        labels = []

        for m in measure_list:
            if isinstance(m, dict):
                fn = m.get("fn", "").upper()
                field_name = m.get("field")
                label = m.get("label")

                field_label = get_verbose(field_name) if field_name else "Records"

                if label:
                    labels.append(label)
                elif fn and field_label:
                    labels.append(f"{fn} of {field_label}")
                else:
                    labels.append(field_label)

            else:
                labels.append(str(m))

        return labels

    def map_filters(filter_list):
        OP_MAP = {
            "exact": "=",
            "iexact": "=",
            "contains": "contains",
            "icontains": "contains",
            "gt": ">",
            "gte": "≥",
            "lt": "<",
            "lte": "≤",
            "in": "in",
            "range": "between",
            "isnull": "is empty",
        }

        labels = []

        for f in filter_list:
            if not isinstance(f, dict):
                labels.append(str(f))
                continue

            field_name = f.get("field")
            field_label = get_verbose(field_name)

            op = f.get("op", "exact")
            value = resolve_value(field_name, f.get("value"))

            op_label = OP_MAP.get(op, op)

            if op == "isnull":
                label = f"{field_label} {op_label}"
            elif isinstance(value, list):
                label = f"{field_label} {op_label} ({', '.join(map(str, value))})"
            else:
                label = f"{field_label} {op_label} {value}"

            labels.append(label)

        return labels

    # ===== FINAL CONTEXT =====
    return {
        "spec": raw,
        "effective_limit": report.limit or raw.get("limit"),
        "verbose": {
            "fields": map_fields(raw.get("fields", [])),
            "row_groups": map_group_fields(raw.get("row_groups", [])),
            "col_groups": map_group_fields(raw.get("col_groups", [])),
            "measures": map_measures(raw.get("measures", [])),
            "filters": map_filters(raw.get("filters", [])),
        }
    }
class ReportDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Report
    slug_field = "slug"
    slug_url_kwarg = "slug"
    template_name = "reports/detail.html"
    context_object_name = "report"
    permission_required = "reports.view_report"
    raise_exception = False

    def handle_no_permission(self):
        return HttpResponse(
            "<h3>❌ You don't have permission to view this report.</h3>",
            status=403
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(build_verbose_spec(self.object))

        return ctx
    

class ReportDeleteView(LoginRequiredMixin,PermissionRequiredMixin, DeleteView):
    model = Report
    slug_field = "slug"
    slug_url_kwarg = "slug"
    template_name = "reports/delete_confirm.html"
    success_url = reverse_lazy("reports:list")
    permission_required = "reports.delete_report"
    raise_exception = False 
    def handle_no_permission(self):
        return HttpResponse(
            "<h3>❌ You don't have permission to delete this report.</h3>",
            status=403
        )

@login_required
def run_report(request, slug: str):

    if not request.user.has_perm("reports.view_report"):
        return HttpResponse(
            "<h3>❌ You don't have permission to view this report.</h3>",
            status=403
        )

    rep = get_object_or_404(Report, slug=slug, is_active=True)
    spec = ReportSpec.from_dict(rep.spec)

    # 🔥 CORE ENGINE (DO NOT TOUCH STRUCTURE)
    payload = ReportEngine().run(spec, user=request.user)

    # MODEL MAP
    app_label, model_name = spec.model.split(".")
    model = apps.get_model(app_label, model_name)

    field_map = {}
    for f in model._meta.get_fields():
        if hasattr(f, "verbose_name"):
            field_map[f.name] = f.verbose_name.title()

    # HEADER LABELS ONLY
    payload["header_labels"] = [
        field_map.get(h, h.replace("_", " ").title())
        for h in payload.get("headers", [])
    ]

    payload["group_labels"] = [
        field_map.get(k, k.replace("_", " ").title())
        for k in payload.get("group_keys", [])
    ]

    extra_ctx = build_verbose_spec(rep)

    return render(
        request,
        "reports/run.html",
        {
            "report": rep,
            "payload": payload,
            **extra_ctx,
        }
    )


@login_required
@require_GET
def run_report_api(request, slug: str):

    if not request.user.has_perm("reports.view_report"):
        return JsonResponse({"error": "Permission denied"}, status=403)

    rep = get_object_or_404(Report, slug=slug, is_active=True)
    spec = ReportSpec.from_dict(rep.spec)

    payload = ReportEngine().run(spec, user=request.user)

    # MODEL MAP
    app_label, model_name = spec.model.split(".")
    model = apps.get_model(app_label, model_name)

    field_map = {}
    choice_map = {}
    fk_fields = {}

    for f in model._meta.get_fields():
        if hasattr(f, "verbose_name"):
            field_map[f.name] = f.verbose_name.title()

        if hasattr(f, "choices") and f.choices:
            choice_map[f.name] = dict(f.choices)

        if f.is_relation and f.many_to_one:
            fk_fields[f.name] = f.related_model

    # FORMAT VALUE
    def format_value(field, value):
        if value is None:
            return ""

        if isinstance(value, datetime):
            if timezone.is_aware(value):
                value = timezone.localtime(value)
            return value.strftime("%d-%m-%Y %I:%M %p")

        if isinstance(value, date):
            return value.strftime("%d-%m-%Y")

        if field in choice_map:
            return choice_map[field].get(value, value)

        if field in fk_fields:
            obj = fk_fields[field].objects.filter(pk=value).first()
            if obj:
                if hasattr(obj, "first_name") or hasattr(obj, "last_name"):
                    full_name = f"{getattr(obj, 'first_name', '')} {getattr(obj, 'last_name', '')}".strip()
                    if full_name:
                        return full_name
                if hasattr(obj, "username"):
                    return obj.username
                return str(obj)

        if isinstance(value, bool):
            return "Yes" if value else "No"

        if isinstance(value, str):
            return value.replace("_", " ")

        return value

    # HEADERS
    if payload.get("view") == "summary":
        headers = payload.get("group_keys", []) + payload.get("measure_labels", [])
    else:
        headers = payload.get("headers", [])

    raw_rows = payload.get("rows", [])

    normalized_rows = [
        r if isinstance(r, dict) else dict(zip(headers, r))
        for r in raw_rows
    ]

    # MATRIX PROCESSING
    original_matrix_rows = payload.get("rows", [])
    original_matrix_cols = payload.get("cols", [])

    if payload.get("view") == "matrix":
        
        def normalize(v):
            return str(v).strip().lower().replace("_", " ")

        filters = spec.filters or []
        order = []

        for f in filters:
            op = getattr(f, "op", None)
            value = getattr(f, "value", None)

            if op == "in" and value:
                if isinstance(value, str):
                    order = [v.strip() for v in value.split(",") if v.strip()]
                else:
                    order = value
                break

        if order:

            order = [normalize(v) for v in order]

            col_map = {}

            for col in original_matrix_cols:
                for field, val in col:
                    display_val = normalize(format_value(field, val))
                    col_map[display_val] = col

            new_cols = []

            for val in order:
                col = col_map.get(val)
                if col and col not in new_cols:
                    new_cols.append(col)

            for col in original_matrix_cols:
                if col not in new_cols:
                    new_cols.append(col)

            original_matrix_cols = new_cols

        main_measure = payload["measure_labels"][0]

        col_names = [
            " / ".join(str(format_value(field, v)) for field, v in col)
            for col in original_matrix_cols
        ]

        headers = ["row_label"] + col_names + ["row_total"]

        normalized_rows = []

        for rk in original_matrix_rows:

            rkey = str(rk)

            row_label = " / ".join(
                str(format_value(field, value))
                for field, value in rk
            )

            row_data = {"row_label": row_label}
            row_total = 0

            for ck, col_name in zip(original_matrix_cols, col_names):

                ckey = str(ck)

                val = (
                    payload.get("cell_nested", {})
                    .get(rkey, {})
                    .get(ckey, {})
                    .get(main_measure, 0)
                )

                row_data[col_name] = val
                row_total += val

            row_data["row_total"] = row_total
            normalized_rows.append(row_data)

    # SEARCH
    search = request.GET.get("search", "").lower()
    if search:
        normalized_rows = [
            r for r in normalized_rows
            if any(search in str(v).lower() for v in r.values())
        ]

    # HEADER LABELS
    header_labels = []

    if payload.get("view") == "matrix":

        # ✅ CORRECT SOURCE (original rows)
        row_fields = [f for f, _ in original_matrix_rows[0]] if original_matrix_rows else []

        row_label_name = " / ".join(
            field_map.get(f, f.replace("_", " ").title())
            for f in row_fields
        ) if row_fields else "Row"

        for h in headers:
            if h == "row_label":
                header_labels.append(row_label_name)
            else:
                header_labels.append(
                    field_map.get(
                        h,
                        h.replace("_", " ").upper() if len(h) <= 4 else h.replace("_", " ").title()
                    )
                )

    else:
        header_labels = [
            field_map.get(
                h,
                h.replace("_", " ").upper() if len(h) <= 4 else h.replace("_", " ").title()
            )
            for h in headers
        ]

    # SORT
    sort = request.GET.get("sort")
    order = request.GET.get("order", "asc")

    if sort:
        reverse = order == "desc"

        def sort_key(x):
            val = x.get(sort)
            if val is None:
                return (1, "")
            try:
                return (0, float(val))
            except:
                return (0, str(val).lower())

        normalized_rows = sorted(normalized_rows, key=sort_key, reverse=reverse)

    # PAGINATION
    limit_param = request.GET.get("limit")
    offset = int(request.GET.get("offset", 0))

    total = len(normalized_rows)

    if not limit_param or limit_param in ["all", "NaN", "undefined"]:
        page_rows = normalized_rows
    else:
        try:
            limit = int(limit_param)
        except:
            limit = 10

        page_rows = normalized_rows[offset: offset + limit]

    # FINAL FORMAT
    rows = []
    for row in page_rows:
        formatted = {k: format_value(k, v) for k, v in row.items()}
        rows.append(formatted)
        
    measure_fields = payload.get("measure_labels", [])
    group_fields = payload.get("group_keys", [])    

    # RESPONSE
    return JsonResponse({
        "total": total,
        "rows": rows,
        "headers": headers,
        "header_labels": header_labels,
        # 🔥 ADD THIS
        "measure_fields": measure_fields,
        "group_fields": group_fields,
        "header_map": {
            h: field_map.get(h, h.replace("_", " ").title())
            for h in headers
        }
    })

# Export Report CSV with corrected filter lookups
@login_required
def export_report_csv(request, slug):
    rep = get_object_or_404(Report, slug=slug, is_active=True)
    spec = ReportSpec.from_dict(rep.spec)
    payload = ReportEngine().run(spec, user=request.user)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename=\"{rep.slug}.csv\"'
    w = csv.writer(response)

    view = payload.get("view")

    # 1) TABULAR EXPORT
    if view == "tabular":
        headers = payload["headers"]
        rows = payload["rows"]

        w.writerow(headers)
        for row in rows:
            w.writerow([row.get(h, "") for h in headers])

        return response

    # 2) SUMMARY EXPORT
    if view == "summary":
        group_keys = payload["group_keys"]
        measure_labels = payload["measure_labels"]
        measure_titles = payload.get("measure_titles", {})

        # Build header row
        headers = group_keys + [
            measure_titles.get(lbl, lbl) for lbl in measure_labels
        ]
        w.writerow(headers)

        # Data rows
        for row in payload["rows"]:
            w.writerow(
                [row.get(k, "") for k in group_keys] +
                [row.get(m, "") for m in measure_labels]
            )

        # Footer (Grand Total)
        grand = payload["grand_total"]
        w.writerow(
            ["Grand Total"] +
            [""] * (len(group_keys) - 1) +
            [grand.get(m, "") for m in measure_labels]
        )

        return response

    # 3) MATRIX EXPORT
    if view == "matrix":
        main_measure = payload["measure_labels"][0]

        cols = payload["cols"]       # column group tuples
        rows = payload["rows"]       # row group tuples
        cell = payload["cell_nested"]
        row_totals = payload["row_totals"]
        col_totals = payload["col_totals"]
        grand = payload["grand_total"]

        # Convert col tuple → readable label
        col_headers = [
            " / ".join([str(v) for a, v in ck]) for ck in cols
        ]

        # Write header row
        w.writerow([" "] + col_headers + ["Row Total"])

        # Rows
        for rk in rows:
            rkey = str(rk)
            row_label = " / ".join([str(v) for a, v in rk])

            row_values = []
            for ck in cols:
                ckey = str(ck)
                val = (
                    cell.get(rkey, {})
                        .get(ckey, {})
                        .get(main_measure, 0)
                )
                row_values.append(val)

            row_total = row_totals.get(rkey, {}).get(main_measure, 0)

            w.writerow([row_label] + row_values + [row_total])

        # Footer totals
        col_values = [
            col_totals.get(str(ck), {}).get(main_measure, 0)
            for ck in cols
        ]
        w.writerow(["Column Total"] + col_values + [grand.get(main_measure, 0)])

        return response

    return HttpResponse("Unknown report type", status=400)



# MTD Report View by Ashutosh
User = get_user_model()

STATUS_HEADERS = [
    "Approved", "Gross Disbursed", "Net Disbursed",
    "OFB", "Underwriting", "Reject Relook", "Declined"
]

ASSIGNMENT_TYPES = [
    ("business_head", "Business Head"),
    ("business_manager", "Business Manager"),
    ("sm", "Sales Manager"),
    ("team_lead", "Team Leader"),
    ("tele_sales_executive", "TSE"),
]

# Mapping from field name to related_name for reverse lookup in User dropdown
ASSIGNMENT_RELATED_NAMES = {
    "business_head": "business_head_leads",
    "business_manager": "business_manager_leads",
    "sm": "sm_leads",
    "team_lead": "team_leads",
    "tele_sales_executive": "tele_sales_exec_leads",
}


# Allowed statuses (match your DB casing)
ALLOWED_STATUSES = [
    "approved",
    "disbursed",
    "ofb",
    "underwriting",
    "reject_relook",
    "Declined",
]


@login_required
def ajax_users_by_assignment_field(request):
    """
    Return users for a given assignment field.
    Optionally filter by channel_name (if provided and not 'all').
    Only includes users linked to at least one lead in ALLOWED_STATUSES.
    """
    assignment_field = request.GET.get("assignment_field")
    channel_name = request.GET.get("channel_name")  # optional

    # Validate assignment_field
    if not assignment_field or assignment_field not in ASSIGNMENT_RELATED_NAMES:
        return JsonResponse({"users": []})

    rel_name = ASSIGNMENT_RELATED_NAMES[assignment_field]

    
    filter_kwargs = {f"{rel_name}__status__in": ALLOWED_STATUSES}

    # Apply channel filter only if valid
    if channel_name and channel_name.lower() != "all":
        filter_kwargs[f"{rel_name}__channel_name"] = channel_name

    # Fetch users linked to matching leads
    users = (
        User.objects.filter(**filter_kwargs)
        .distinct()
        .only("id", "first_name", "last_name", "username")
        .order_by("first_name")
    )

    # Prepare JSON response
    users_list = [
        {"id": u.id, "name": u.get_full_name() or u.username}
        for u in users
    ]

    return JsonResponse({"users": users_list})


@login_required
def mtd_report_view(request):
    # -------------------- Filters --------------------
    assignment_type = request.GET.get("assignment_type")
    report_type = request.GET.get("report_type", "sum")
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")
    assignment_field = request.GET.get("assignment_field")
    assignment_value = request.GET.get("assignment_value")

    allowed_types = {at[0] for at in ASSIGNMENT_TYPES}
    if assignment_type not in allowed_types:
        assignment_type = None

    # -------------------- Base queryset --------------------
    qs = get_visible_queryset(Lead, request.user)

    # -------------------- Date Filtering --------------------
    if start_date and end_date:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
        qs = qs.filter(
                        (
                           Q(status__in=["approved", "ofb", "underwriting", 
                                      "reject_relook", "Declined"]) & 
                            Q(dos__range=(start_dt, end_dt))
                        )
                        |
                        (
                            Q(status="disbursed")  & 
                            Q(dod__range=(start_dt, end_dt))
                        )
                ).distinct()

    # -------------------- Assignment Filtering --------------------
    if assignment_field and assignment_value and assignment_field in allowed_types:
        qs = qs.filter(**{f"{assignment_field}__id": int(assignment_value)})

    # -------------------- Annotation Helper --------------------
    def get_aggregates(mode="sum"):
        if mode == "count":
            return dict(
                approved=Count(Case(When(status="approved", then=1))),
                gross_disbursed=Count(Case(When(status="disbursed", then=1))),
                net_disbursed=Count(Case(When(status="disbursed", then=1))),
                ofb=Count(Case(When(status="ofb", then=1))),
                underwriting=Count(Case(When(status="underwriting", then=1))),
                reject_relook=Count(Case(When(status="reject_relook", then=1))),
                declined=Count(Case(When(status="Declined", then=1))),
            )
        else:
            return dict(
                approved=Sum(Case(When(status="approved", then=F("approved_amount")))),
                gross_disbursed=Sum(Case(When(status="disbursed", then=F("gross_disbursed")))),
                net_disbursed=Sum(Case(When(status="disbursed", then=F("net_disbursed")))),
                ofb=Sum(Case(When(status="ofb", then=F("login_amount")))),
                underwriting=Sum(Case(When(status="underwriting", then=F("login_amount")))),
                reject_relook=Sum(Case(When(status="reject_relook", then=F("login_amount")))),
                declined=Sum(Case(When(status="Declined", then=F("login_amount")))),
            )

    # -------------------- Totals --------------------
    totals = qs.aggregate(**get_aggregates(report_type))
    totals["grand_total"] = sum(v or 0 for v in totals.values())


    # -------------------- Grouped Rows --------------------
    rows = []
    if assignment_type:
        qs_grouped = qs.values(
            assignment_type,
            f"{assignment_type}__first_name",
            f"{assignment_type}__last_name",
            f"{assignment_type}__username",
        ).annotate(**get_aggregates(report_type))

        # Prefetch user profiles in batch
        user_ids = [row[assignment_type] for row in qs_grouped if row[assignment_type]]
        profiles = {p.user_id: p for p in UserProfile.objects.filter(user_id__in=user_ids)}

        for row in qs_grouped:
            uid = row[assignment_type]
            if not uid:
                continue
            user_name = (
                f"{row.get(f'{assignment_type}__first_name', '')} "
                f"{row.get(f'{assignment_type}__last_name', '')}".strip()
                or row.get(f"{assignment_type}__username")
                or "User"
            )
            grand_total = sum([row.get(k) or 0 for k in get_aggregates(report_type).keys()])
            rows.append({
                "user": user_name,
                "user_id": uid,
                "profile": profiles.get(uid),
                **{k: row.get(k) or 0 for k in get_aggregates(report_type).keys()},
                "grand_total": grand_total,
            })

    # -------------------- Sorting --------------------
    sort_field = request.GET.get("sort", "user")
    order = request.GET.get("order", "asc").lower()
    allowed_sort_fields = [
        "user", "ofb", "underwriting", "declined", "reject relook",
        "approved", "gross disbursed", "net disbursed", "grand total"
    ]
    if sort_field not in allowed_sort_fields:
        sort_field = "user"
    reverse = order == "desc"
    rows.sort(
        key=lambda x: x.get(sort_field.replace(" ", "_"), 0) if sort_field != "user" else x["user"].lower(),
        reverse=reverse
    )

    # -------------------- Export to Excel --------------------
    if request.GET.get("export"):
        return export_mtd_excel(rows, assignment_type, report_type)

    # -------------------- Context --------------------
    context = {
        "report_rows": rows,
        "status_headers": STATUS_HEADERS + ["Grand Total"],
        "assignment_type": assignment_type,
        "report_type": report_type,
        "assignment_types": ASSIGNMENT_TYPES,
        "start_date": start_date,
        "end_date": end_date,
        "totals": totals,
        "sort_fields": allowed_sort_fields,
        "sort_field": sort_field,
        "order": order,
        "assignment_field": assignment_field,
        "assignment_value": assignment_value,
    }
    return render(request, "mtd_reports/mtd_report.html", context)


def export_mtd_excel(rows, assignment_type, report_type):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "MTD Report"

    headers = ["User"] + STATUS_HEADERS + ["Grand Total"]
    ws.append(headers)

    for row in rows:
        ws.append([
            row.get("user"),
            row.get("approved"),
            row.get("gross_disbursed"),
            row.get("net_disbursed"),
            row.get("ofb"),
            row.get("underwriting"),
            row.get("reject_relook"),
            row.get("declined"),
            row.get("grand_total"),
        ])

    for i, column_cells in enumerate(ws.columns, 1):
        length = max(len(str(cell.value)) for cell in column_cells)
        ws.column_dimensions[get_column_letter(i)].width = length + 2

    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = f'attachment; filename=MTD_Report_{datetime.now().strftime("%Y%m%d")}.xlsx'
    wb.save(response)
    return response


@login_required
def mtd_user_detail_view(request, user_id):
    from django.db.models import Sum, F, Q
    from django.core.paginator import Paginator

    user = get_object_or_404(User, id=user_id)

    # -------------------- Filters --------------------
    assignment_type = request.GET.get("assignment_type")
    status = request.GET.get("status")
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")
    assignment_field = request.GET.get("assignment_field")
    assignment_value = request.GET.get("assignment_value")

    allowed_assignment_types = [
        "business_head", "business_manager", "sm",
        "team_lead", "tele_sales_executive"
    ]

    # -------------------- Base queryset --------------------
    qs = get_visible_queryset(Lead, request.user).select_related(
        "business_head", "business_manager", "sm",
        "team_lead", "tele_sales_executive"
    )

    # -------------------- Filter by assignment type / user --------------------
    if assignment_type:
        qs = qs.filter(**{assignment_type: user})
    else:
        q_filters = Q()
        for at in allowed_assignment_types:
            q_filters |= Q(**{at: user})
        qs = qs.filter(q_filters)

    # -------------------- Filter by assignment_field + assignment_value --------------------
    if assignment_field and assignment_value:
        try:
            assignment_value = int(assignment_value)
            if assignment_field in allowed_assignment_types:
                qs = qs.filter(**{f"{assignment_field}__id": assignment_value})
        except ValueError:
            pass

    # -------------------- Filter by status --------------------
    if status:
        qs = qs.filter(status=status)
    else:
        qs = qs.filter(status__in=ALLOWED_STATUSES)

    # -------------------- Date Filters --------------------
    if start_date and end_date:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
        if status == "disbursed":
            qs = qs.filter(dod__range=(start_dt, end_dt))
        elif status in ALLOWED_STATUSES:
            qs = qs.filter(dos__range=(start_dt, end_dt))
        else:
            qs1 = qs.filter(dos__range=(start_dt, end_dt), status__in=ALLOWED_STATUSES)
            qs2 = qs.filter(dod__range=(start_dt, end_dt), status="disbursed")
            qs = qs1.union(qs2)

    
    # -------------------- Sorting (keep current logic) --------------------
    sort_field = request.GET.get("sort", "id")
    order = request.GET.get("order", "asc").lower()
    reverse = order == "desc"

    numeric_sort_fields = [
        "id", "approved_amount", "gross_disbursed", "net_disbursed",
        "login_amount", "require_loan_amount"
    ]

    if sort_field in numeric_sort_fields + ["grand_total"]:
        qs = qs.order_by(F(sort_field).desc() if reverse else F(sort_field).asc())
    elif sort_field in ["name", "status", "business_head", "business_manager", "sm", "team_lead", "tele_sales_executive"]:
        qs = qs.order_by(F(sort_field).desc() if reverse else F(sort_field).asc())
    else:
        qs = qs.order_by("-dos")

    qs_all = qs
    # -------------------- Grand Totals --------------------
    totals = qs_all.aggregate(
        total_approved=Sum(F("approved_amount")),
        total_gross_disbursed=Sum(F("gross_disbursed")),
        total_net_disbursed=Sum(F("net_disbursed")),
        total_login=Sum(F("login_amount")),
    )

    totals["grand_total"] = sum([
        totals.get("total_approved") or 0,
        totals.get("total_gross_disbursed") or 0,
        totals.get("total_net_disbursed") or 0,
        totals.get("total_login") or 0,
    ])

    # -------------------- Labels --------------------
    assignment_labels = {
        "business_head": "Business Head",
        "business_manager": "Business Manager",
        "sm": "Sales Manager",
        "team_lead": "Team Leader",
        "tele_sales_executive": "Tele Sales Executive",
        "backend_executive_user": "Backend Executive",
    }
    assignment_label = assignment_labels.get(assignment_type, "All Assignment Types") if assignment_type else "All Assignment Types"
    status_label = dict(Lead._meta.get_field("status").choices).get(status, status) if status else None

    # -------------------- Pagination --------------------
    # paginator = Paginator(qs, 100)
    # page_number = request.GET.get("page", 1)
    # page_obj = paginator.get_page(page_number)

    # -------------------- Sortable Fields --------------------
    sortable_fields = [
        {"field": "id", "label": "#"},
        {"field": "name", "label": "Applicant"},
        {"field": "status", "label": "Status"},
        {"field": "approved_amount", "label": "Approved"},
        {"field": "gross_disbursed", "label": "Gross Disb"},
        {"field": "net_disbursed", "label": "Net Disb"},
        {"field": "login_amount", "label": "Login Amount"},
        {"field": "lender_name", "label": "Lender"},
        {"field": "business_head", "label": "Business Head"},
        {"field": "business_manager", "label": "Business Manager"},
        {"field": "sm", "label": "Sales Manager"},
        {"field": "team_lead", "label": "Team Lead"},
        {"field": "tele_sales_executive", "label": "Tele Sales Exec"},
        {"field": "dos", "label": "DOS"},
        {"field": "dod", "label": "DOD"},
    ]

    # -------------------- Context --------------------
    context = {
        "user": user,
        "assignment_type": assignment_type,
        "assignment_label": assignment_label,
        "status": status,
        "status_label": status_label,
        "assignment_value": assignment_value,
        "assignment_field": assignment_field,
        "leads": qs,
        "start_date": start_date,
        "end_date": end_date,
        "totals": totals,
        "sort_field": sort_field,
        "order": order,
        "sortable_fields": sortable_fields,
    }

    return render(request, "mtd_reports/mtd_user_detail.html", context)


# MTD WIP REPORT
@login_required
def mtd_wip_report_view(request):
    # -------------------- Filters --------------------
    report_type = request.GET.get("report_type", "sum")  # 'sum' or 'count'
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")
    assignment_field = request.GET.get("assignment_field")
    assignment_value = request.GET.get("assignment_value")
    channel_name = request.GET.get("channel_name","")  # optional filter now
    sort_by = request.GET.get("sort_by", "lender")
    sort_order = request.GET.get("sort_order", "asc")

    # -------------------- Base queryset --------------------
    qs = get_visible_queryset(Lead, request.user)

    # -------------------- Channel Filtering --------------------
    if channel_name and channel_name.lower() != "all":
        qs = qs.filter(channel_name=channel_name)
    elif channel_name and channel_name.lower() == "all":
        pass  
    else:
        qs = qs.none()  

    # -------------------- Date Filtering --------------------
    if start_date and end_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
            qs = qs.filter(
                (
                    Q(status__in=["approved", "ofb", "underwriting", "reject_relook", "Declined"])
                    & Q(dos__range=(start_dt, end_dt))
                )
                |
                (
                    Q(status="disbursed")
                    & Q(dod__range=(start_dt, end_dt))
                )
            ).distinct()
        except ValueError:
            pass

    # -------------------- Assignment Field Filter --------------------
    if assignment_field and assignment_value:
        try:
            assignment_value = int(assignment_value)
            if assignment_field in dict(ASSIGNMENT_TYPES):
                qs = qs.filter(**{f"{assignment_field}__id": assignment_value})
        except ValueError:
            pass

    # -------------------- Helper: Aggregation --------------------
    def annotate_query(qs, mode="sum"):
        if mode == "count":
            return qs.annotate(
                approved=Count(Case(When(status="approved", then=1))),
                ofb=Count(Case(When(status="ofb", then=1))),
                reject_relook=Count(Case(When(status="reject_relook", then=1))),
                underwriting=Count(Case(When(status="underwriting", then=1))),
                gross_disbursed=Count(Case(When(status="disbursed", then=1))),
                net_disbursed=Count(Case(When(status="disbursed", then=1))),
            )
        else:
            return qs.annotate(
                approved=Sum(Case(When(status="approved", then=F("approved_amount")))),
                ofb=Sum(Case(When(status="ofb", then=F("login_amount")))),
                reject_relook=Sum(Case(When(status="reject_relook", then=F("login_amount")))),
                underwriting=Sum(Case(When(status="underwriting", then=F("login_amount")))),
                gross_disbursed=Sum(Case(When(status="disbursed", then=F("gross_disbursed")))),
                net_disbursed=Sum(Case(When(status="disbursed", then=F("net_disbursed")))),
            )

    # -------------------- Group by lender --------------------
    qs_grouped = qs.values("lender_name__id", "lender_name__name")
    qs_grouped = annotate_query(qs_grouped, report_type)

    # -------------------- Prepare Rows --------------------
    rows = []
    totals = {
        key: 0 for key in [
            "approved", "ofb", "reject_relook", "underwriting",
            "gross_disbursed", "net_disbursed", "grand_total"
        ]
    }

    for row in qs_grouped:
        lender_name = row["lender_name__name"] or "(No Lender)"
        lender_id = row["lender_name__id"] or 0
        approved = row["approved"] or 0
        ofb = row["ofb"] or 0
        reject_relook = row["reject_relook"] or 0
        underwriting = row["underwriting"] or 0
        gross_disbursed = row["gross_disbursed"] or 0
        net_disbursed = row["net_disbursed"] or 0
        grand_total = approved + ofb + reject_relook + underwriting + gross_disbursed + net_disbursed

        if any([approved, ofb, reject_relook, underwriting, gross_disbursed, net_disbursed]):
            rows.append({
                "lender": lender_name,
                "lender_id": lender_id,
                "approved": approved,
                "ofb": ofb,
                "reject_relook": reject_relook,
                "underwriting": underwriting,
                "gross_disbursed": gross_disbursed,
                "net_disbursed": net_disbursed,
                "grand_total": grand_total,
            })
            for k in totals.keys():
                totals[k] += locals().get(k, 0)

    rows.append({"lender": "Grand Total", **totals})

    # -------------------- Sorting --------------------
    sortable_rows = rows[:-1]
    reverse = sort_order == "desc"

    if sort_by in ["lender", "approved", "ofb", "reject_relook", "underwriting", "gross_disbursed", "net_disbursed", "grand_total"]:
        if sort_by == "lender":
            sortable_rows.sort(key=lambda x: (x["lender"] or "").lower(), reverse=reverse)
        else:
            sortable_rows.sort(key=lambda x: x[sort_by] or 0, reverse=reverse)

    rows = sortable_rows + [rows[-1]]

    # -------------------- Export to Excel --------------------
    if request.GET.get("export") == "1":
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "WIP Channel Report"

        headers = [
            "Lender", "Approved", "OFB", "Reject Relook", "Underwriting",
            "Net Disbursed", "Gross Disbursed", "Grand Total"
        ]
        ws.append(headers)

        for r in rows:
            ws.append([
                r["lender"], r["approved"], r["ofb"], r["reject_relook"],
                r["underwriting"], r["net_disbursed"], r["gross_disbursed"], r["grand_total"]
            ])

        for i, col in enumerate(ws.columns, 1):
            max_length = max(len(str(cell.value)) if cell.value else 0 for cell in col)
            ws.column_dimensions[get_column_letter(i)].width = min(40, max(10, max_length + 2))

        filename = f"{channel_name or 'all_channels'}_wip_lender_report.xlsx"
        response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        wb.save(response)
        return response

    # -------------------- Users for assignment_field dropdown --------------------
    if assignment_field in ASSIGNMENT_RELATED_NAMES:
        rel_name = ASSIGNMENT_RELATED_NAMES[assignment_field]
        users_for_field = User.objects.filter(**{f"{rel_name}__isnull": False}).distinct().order_by("username")
    else:
        users_for_field = User.objects.none()

    # -------------------- Render --------------------
    return render(request, "mtd_reports/mtd_wip_report.html", {
        "rows": rows,
        "status_headers": ["Approved", "OFB", "Reject Relook", "Underwriting", "Net Disbursed", "Gross Disbursed", "Grand Total"],
        "channel_choices": CHANNEL_CHOICES,
        "channel_name": channel_name,
        "start_date": start_date,
        "end_date": end_date,
        "report_type": report_type,
        "sort_by": sort_by,
        "sort_order": sort_order,
        "assignment_types": ASSIGNMENT_TYPES,
        "assignment_field": assignment_field,
        "assignment_value": assignment_value,
        "users_for_field": users_for_field,
    })

@login_required
def mtd_wip_lender_detail_view(request, lender_id=None):
    """
    Detail view for a specific lender in MTD WIP Report.
    Shows all channels by default (filters only when channel_name is selected).
    """

    # -------------------- Filters --------------------
    status = request.GET.get("status")
    channel_name = request.GET.get("channel_name", "")
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")
    assignment_field = request.GET.get("assignment_field")
    assignment_value = request.GET.get("assignment_value")

    # -------------------- Base queryset --------------------
    qs = get_visible_queryset(Lead, request.user)
    lender = None

    # -------------------- Lender filter --------------------
    if lender_id is not None:
        if int(lender_id) == 0:
            qs = qs.filter(lender_name__isnull=True)
        else:
            lender = get_object_or_404(Bank, id=lender_id)
            qs = qs.filter(lender_name=lender)

    # -------------------- Assignment Field + Value --------------------
    if assignment_field and assignment_value:
        try:
            assignment_value = int(assignment_value)
            qs = qs.filter(**{f"{assignment_field}__id": assignment_value})
        except ValueError:
            pass

    # -------------------- Status filter --------------------
    if status:
        qs = qs.filter(status=status)
    else:
        qs = qs.filter(status__in=ALLOWED_STATUSES)

    # -------------------- Channel filter --------------------
    if channel_name and channel_name.lower() != "all":
        qs = qs.filter(channel_name=channel_name)
    elif channel_name and channel_name.lower() == "all":
        pass  
    else:
        qs = qs.none()    
    # else: show all channels (no filter)

    # -------------------- Date Filters --------------------
    if start_date and end_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()

            if status == "disbursed":
                # For disbursed, filter by DOD
                qs = qs.filter(dod__range=(start_dt, end_dt))
            elif status in ALLOWED_STATUSES:
                # For allowed statuses, filter by DOS
                qs = qs.filter(dos__range=(start_dt, end_dt))
            else:
                # If no specific status, include both DOS and DOD ranges
                qs = qs.filter(
                    (
                        Q(status__in=ALLOWED_STATUSES)
                        & Q(dos__range=(start_dt, end_dt))
                    )
                    |
                    (
                        Q(status="disbursed")
                        & Q(dod__range=(start_dt, end_dt))
                    )
                ).distinct()
        except ValueError:
            pass

    # -------------------- Sorting --------------------
    sort_field = request.GET.get("sort", "id")
    order = request.GET.get("order", "asc").lower()
    reverse = order == "desc"

    numeric_sort_fields = [
        "id", "approved_amount", "gross_disbursed", "net_disbursed",
        "login_amount", "require_loan_amount"
    ]

    if sort_field in numeric_sort_fields or sort_field in ["name", "status", "channel_name", "lender_name"]:
        qs = qs.order_by(F(sort_field).desc() if reverse else F(sort_field).asc())
    else:
        qs = qs.order_by("-dos")

    # -------------------- Totals --------------------
    totals = qs.aggregate(
        total_approved=Sum(F("approved_amount")),
        total_login=Sum(F("login_amount")),
        total_required=Sum(F("require_loan_amount")),
        total_gross_disbursed=Sum(F("gross_disbursed")),
        total_net_disbursed=Sum(F("net_disbursed")),
    )

    totals["grand_total"] = sum([
        totals.get("total_approved") or 0,
        totals.get("total_login") or 0,
        totals.get("total_required") or 0,
        totals.get("total_gross_disbursed") or 0,
        totals.get("total_net_disbursed") or 0,
    ])

    # -------------------- Labels --------------------
    status_labels = dict(Lead._meta.get_field("status").choices)
    status_label = status_labels.get(status, status) if status else None
    lender_name = lender.name if lender else "(No Lender)"

    # -------------------- Users for assignment_field dropdown --------------------
    if assignment_field and assignment_field in ASSIGNMENT_RELATED_NAMES:
        rel_name = ASSIGNMENT_RELATED_NAMES[assignment_field]
        users_for_field = User.objects.filter(**{f"{rel_name}__isnull": False}).distinct().order_by("username")
    else:
        users_for_field = User.objects.none()

    # -------------------- Sortable Fields --------------------
    sortable_fields = [
        {"field": "id", "label": "#"},
        {"field": "name", "label": "Applicant"},
        {"field": "status", "label": "Status"},
        {"field": "approved_amount", "label": "Approved"},
        {"field": "gross_disbursed", "label": "Gross Disb"},
        {"field": "net_disbursed", "label": "Net Disb"},
        {"field": "login_amount", "label": "Login Amount"},
        {"field": "lender_name", "label": "Lender"},
        {"field": "channel_name", "label": "Channel"},
        {"field": "dos", "label": "DOS"},
        {"field": "dod", "label": "DOD"},
    ]

    # -------------------- Context --------------------
    context = {
        "lender": lender,
        "lender_name": lender_name,
        "status": status,
        "status_label": status_label,
        "channel_name": channel_name,
        "start_date": start_date,
        "end_date": end_date,
        "leads": qs,
        "totals": totals,
        "assignment_field": assignment_field,
        "assignment_value": assignment_value,
        "users_for_field": users_for_field,
        "sort_field": sort_field,
        "order": order,
        "sortable_fields": sortable_fields,
    }

    return render(request, "mtd_reports/mtd_wip_lender_detail.html", context)

# Lead History View Report

@login_required
def lead_status_history(request):
    User = get_user_model()
    current_user = request.user
    #  PERMISSION CHECK
    if not (
        current_user.has_perm("reports.view_report") and
        current_user.has_perm("crm.view_lead")
    ):
        return HttpResponseForbidden("<h3>You do not have permission to view this report.</h3>")

    # GET PROFILE
    try:
        profile = current_user.userprofile
        role = profile.role
        branch = profile.branch
    except UserProfile.DoesNotExist:
        profile = None
        role = None
        branch = None

    # ADMIN LOGIC
    if current_user.is_superuser or role == "Admin":
        users = User.objects.filter(is_active=True).order_by("username")

    else:
        # NORMAL USER
        if branch:
            users = User.objects.filter(
                is_active=True,
                userprofile__branch=branch
            ).order_by("username")
        else:
            users = User.objects.filter(
                id=current_user.id,
                is_active=True
            )

    return render(request, "reports/lead_status_history.html", {
        "users": users,
        "status_choices": Lead._meta.get_field("status").choices,
    })
    
@login_required
@require_GET
def lead_status_history_api(request):

    current_user = request.user

    # PERMISSION
    if not (
        current_user.has_perm("reports.view_report") and
        current_user.has_perm("crm.view_lead")
    ):
        return HttpResponseForbidden("<h3>You do not have permission to view this report.</h3>")

    # INPUTS
    start_date = request.GET.get("start_date") or None
    end_date = request.GET.get("end_date") or None

    if (start_date and not end_date) or (end_date and not start_date):
        return JsonResponse({"error": "Please select both Start Date and End Date"}, status=400)

    user_id = request.GET.get("user_id") or None
    new_status_list = request.GET.getlist("new_status")
    if not new_status_list:
        new_status_list = None

    # table params
    limit = request.GET.get("limit")
    offset = int(request.GET.get("offset", 0))
    sort = request.GET.get("sort")
    order = request.GET.get("order", "desc")
    search = request.GET.get("search")

    # REQUIRE AT LEAST ONE FILTER
    if not any([start_date, end_date, user_id, new_status_list, search]):
        return JsonResponse({"total": 0, "rows": []})

    # DATE
    start_dt = None
    end_dt = None

    if start_date and end_date:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)

    # VISIBLE LEADS
    visible_qs = get_visible_queryset(Lead, current_user)
    lead_ids = list(visible_qs.values_list("id", flat=True))

    if not lead_ids:
        return JsonResponse({"total": 0, "rows": []})

    # STATUS LABEL SQL
    STATUS_MAP = dict(Lead._meta.get_field("status").choices)

    status_case_curr = "CASE curr.status "
    status_case_prev = "CASE prev.status "

    for key, label in STATUS_MAP.items():
        status_case_curr += f"WHEN '{key}' THEN '{label}' "
        status_case_prev += f"WHEN '{key}' THEN '{label}' "

    status_case_curr += "ELSE curr.status END"
    status_case_prev += "ELSE prev.status END"

    # SORT
    sort_map = {
        "lead_id": "l.id",
        "lead_name": "l.name",
        "old_status": "prev.status",
        "new_status": "curr.status",
        "changed_by": "u.username",
        "changed_at": "curr.history_date"
    }

    sort_column = sort_map.get(sort, "curr.history_date")
    sort_order = "DESC" if order == "desc" else "ASC"

    # SEARCH
    search_term = f"%{search}%" if search else None

    # BASE QUERY
    base_query = f"""
    FROM crm_historicallead curr

    LEFT JOIN crm_historicallead prev 
        ON curr.id = prev.id 
        AND prev.history_date = (
            SELECT MAX(h2.history_date)
            FROM crm_historicallead h2
            WHERE h2.id = curr.id
            AND h2.history_date < curr.history_date
        )

    LEFT JOIN auth_user u 
        ON curr.history_user_id = u.id

    LEFT JOIN crm_lead l 
        ON curr.id = l.id

    WHERE prev.status IS NOT NULL
    AND prev.status <> curr.status

    AND (%s IS NULL OR curr.history_user_id = %s)

    AND (%s IS NULL OR curr.history_date >= %s)
    AND (%s IS NULL OR curr.history_date < %s)

    AND curr.id = ANY(%s)

    AND (%s IS NULL OR curr.status = ANY(%s))

    AND (
        %s IS NULL OR
        l.name ILIKE %s OR
        {status_case_prev} ILIKE %s OR
        {status_case_curr} ILIKE %s OR
        u.username ILIKE %s OR
        u.first_name ILIKE %s OR
        u.last_name ILIKE %s
    )
    """

    params = [
        user_id, user_id,
        start_dt, start_dt,
        end_dt, end_dt,
        lead_ids,
        new_status_list, new_status_list,
        search_term,
        search_term,
        search_term,
        search_term,
        search_term,
        search_term,
        search_term
    ]

    # TOTAL
    count_query = f"SELECT COUNT(*) {base_query}"

    with connection.cursor() as cursor:
        cursor.execute(count_query, params)
        total = cursor.fetchone()[0]

    # MAIN QUERY
    query = f"""
    SELECT 
        l.id AS lead_id,
        l.name AS lead_name,
        prev.status AS old_status,
        curr.status AS new_status,

        TRIM(
            CASE 
                WHEN u.first_name IS NOT NULL AND u.first_name != '' 
                THEN u.first_name || ' ' || COALESCE(u.last_name, '')
                ELSE u.username
            END
        ) AS changed_by,

        curr.history_date AS changed_at

    {base_query}

    ORDER BY {sort_column} {sort_order}
    """

    # PAGINATION
    if limit and limit != "all":
        try:
            limit = int(limit)
            query += " LIMIT %s OFFSET %s"
            params += [limit, offset]
        except:
            pass

    # EXECUTE
    with connection.cursor() as cursor:
        cursor.execute(query, params)
        cols = [c[0] for c in cursor.description]
        data = cursor.fetchall()

    rows = [dict(zip(cols, r)) for r in data]

    # LABEL MAPPING
    for row in rows:
        row["old_status"] = STATUS_MAP.get(row["old_status"], row["old_status"])
        row["new_status"] = STATUS_MAP.get(row["new_status"], row["new_status"])

    return JsonResponse({
        "total": total,
        "rows": rows
    })