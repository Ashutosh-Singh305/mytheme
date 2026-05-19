
from django.db import models
from functools import lru_cache
from typing import List, Tuple

from django.shortcuts import render, redirect
from django.apps import apps
from django.forms import modelform_factory
from django.http import HttpResponseNotFound, HttpResponseForbidden, HttpRequest, HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib import admin, messages
from django.db.models import Model as DjangoModel
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from crm.choices import LEAD_STATUS_CHOICES
from crm.utils import apply_audit_logic, get_allowed_user_queryset,get_visible_queryset
from crm.views import get_accessible_fields
from .models import FieldAccessControl, ListView
from django.core.signals import request_finished
from django.db.models.signals import post_save, post_delete

from django.views.decorators.http import require_GET
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.utils import timezone
from django.utils.dateformat import format as dj_format
from django import forms


# Configuration / constants
NON_FORM_FIELDS = {
    "created_by",
    "modified_by",
    "created_date",
    "modified_at",
}

# cache keys/timeouts (seconds)
CACHE_TIMEOUT_FIELDSETS = 300  # 5 minutes
CACHE_TIMEOUT_FIELD_PERMS = 300  # 5 minutes


# Utility: dynamic model load
def get_model(model_name: str):
    try:
        return apps.get_model("crm", model_name)
    except LookupError:
        return None

def get_rendered_field(Model, obj, f_name):
    meta_field = Model._meta.get_field(f_name)
    value = getattr(obj, f_name, None)

   
    # Empty value
    if value is None:
        return "text", ""

    # ImageField
    if isinstance(meta_field, models.ImageField):
        return "image", value.url if value else ""

  
    # FileField
    if isinstance(meta_field, models.FileField):
        return "file", value.url if value else ""

    # Choices → label
    if meta_field.choices:
        display_method = f"get_{f_name}_display"
        if hasattr(obj, display_method):
            return "text", getattr(obj, display_method)()

    # DateTimeField
    if isinstance(meta_field, models.DateTimeField):
        value = timezone.localtime(value)
        return "text", dj_format(value, "d M Y, h:i A")

    # DateField
    if isinstance(meta_field, models.DateField):
        return "text", dj_format(value, "d M Y")


    return "text", value



# -------------------------
# Admin class lookup (cached)
# -------------------------
@lru_cache(maxsize=128)
def get_admin_class_for_model_label(model_label: str):
    Model = get_model(model_label) if isinstance(model_label, str) else model_label
    if not Model:
        return None
    return admin.site._registry.get(Model).__class__ if Model in admin.site._registry else None

def get_fieldsets_for_model_cached(model_name: str):
    cache_key = f"crm:fieldsets:{model_name}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    Model = get_model(model_name)
    if not Model:
        return None, [], []

    AdminClass = get_admin_class_for_model_label(model_name)
    fieldsets, all_fields, editable_fields = _build_fieldsets_from_admin(
        AdminClass, Model, model_name
    )

    cache_data = (fieldsets, all_fields, editable_fields)
    cache.set(cache_key, cache_data, CACHE_TIMEOUT_FIELDSETS)
    return cache_data

def get_accessible_fields_cached(user_id: int, model_name: str):
    cache_key = f"crm:field_perms:{user_id}:{model_name}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    UserModel = get_user_model()
    try:
        user = UserModel.objects.get(pk=user_id)
    except UserModel.DoesNotExist:
        return set(), set()

    try:
        viewable_fields, editable_fields = get_accessible_fields(user, model_name)
    except Exception:
        viewable_fields, editable_fields = set(), set()

    cache_value = (viewable_fields, editable_fields)
    cache.set(cache_key, cache_value, CACHE_TIMEOUT_FIELD_PERMS)
    return cache_value



# Fieldset extraction (centralized)
def _build_fieldsets_from_admin(AdminClass, Model, model_name: str) -> Tuple[List[dict], List[str], List[str]]:
    raw_fieldsets = getattr(AdminClass, "fieldsets", None) or []

    # Build fieldset list used in template
    fieldsets = []
    all_fieldset_fields = []

    for index, (title, opts) in enumerate(raw_fieldsets, start=1):
        section_id = f"fs_{model_name}_{index}".replace(" ", "_")
        fields = opts.get("fields", []) or []
        flat_fields = []
        for item in fields:
            if isinstance(item, (list, tuple)):
                flat_fields.extend([f for f in item])
            else:
                flat_fields.append(item)
        fieldsets.append({
            "id": section_id,
            "title": title,
            "fields": flat_fields,
        })
        all_fieldset_fields.extend(flat_fields)

    # Fallback to auto fields if no admin fieldsets defined
    if not fieldsets:
        default_id = f"fs_{model_name}_default"
        auto_fields = [
            f.name for f in Model._meta.get_fields()
            if getattr(f, "concrete", True) and not getattr(f, "auto_created", False)
        ]
        fieldsets = [{
            "id": default_id,
            "title": f"{model_name} Information",
            "fields": auto_fields,
        }]
        all_fieldset_fields = auto_fields

    # Remove audit fields and non-editable fields for form building
    ordered_editable_fields = []
    for f_name in all_fieldset_fields:
        if f_name in NON_FORM_FIELDS:
            continue
        try:
            field_obj = Model._meta.get_field(f_name)
            if getattr(field_obj, "editable", True):
                ordered_editable_fields.append(f_name)
        except Exception:
            # ignore missing fields (typos / removed fields)
            continue

    return fieldsets, all_fieldset_fields, ordered_editable_fields


def clear_field_permission_cache(**kwargs):
    cache.clear()


post_save.connect(clear_field_permission_cache, sender=FieldAccessControl)
post_delete.connect(clear_field_permission_cache, sender=FieldAccessControl)

def clear_fieldset_cache(**kwargs):
    cache.clear()

post_save.connect(clear_fieldset_cache, sender=ListView)
post_delete.connect(clear_fieldset_cache, sender=ListView)

# -------------------------
# Field-level hooks using real permissions
# -------------------------
def is_field_visible(user, Model: DjangoModel, field_name: str) -> bool:
    """
    A field is visible if it appears in the user's viewable_fields set.
    """
    viewable_fields, _ = get_accessible_fields_cached(user.pk, Model.__name__)
    if not viewable_fields:
        # default to visible for fields present in the model.
        return field_name in {f.name for f in Model._meta.get_fields()}
    return field_name in viewable_fields


def is_field_editable(user, Model: DjangoModel, field_name: str) -> bool:
    """
    A field is editable if:
    - It is visible (user can see it)
    - AND present in editable_fields set
    """
    viewable_fields, editable_fields = get_accessible_fields_cached(user.pk, Model.__name__)
    if not editable_fields:
        # If no explicit editable rules, assume fields visible are editable (backwards compat).
        return field_name in viewable_fields
    return (field_name in viewable_fields) and (field_name in editable_fields)


# -------------------------
# Helpers for form safety
# -------------------------
def sanitize_post_for_model(user, Model, post_data, allowed_fields, instance=None, bypass_permissions=False):
    safe = {}

    for key, value in post_data.items():
        if key not in allowed_fields:
            continue
        if key in NON_FORM_FIELDS:
            continue

        # ✅ BYPASS permission checks for CREATE
        if not bypass_permissions:
            if not is_field_editable(user, Model, key):
                continue

        # existing logic
        if (
            instance is not None
            and value in ("", None)
            and getattr(instance, key) not in ("", None)
        ):
            continue

        safe[key] = value

    return safe


# Render helper for detail view (pluggable)
def render_field_value(obj, field_name: str):
    try:
        val = getattr(obj, field_name)
    except Exception:
        return None

    field = None
    try:
        field = obj._meta.get_field(field_name)
    except Exception:
        field = None

    # Many-to-many
    if field is not None and getattr(field, "many_to_many", False):
        try:
            return [str(i) for i in val.all()] if val is not None else []
        except Exception:
            return []

    # Boolean formatting
    if isinstance(val, bool):
        return "Yes" if val else "No"

   
    return val


def get_default_listview_pk(model_name: str):
    try:
        lv = ListView.objects.filter(object_name=model_name).first()
        return lv.pk if lv else None
    except Exception:
        return None

def forbidden(request, message):
    return render(
        request,
        "crm/errors/403.html",
        {"message": message},
        status=403
    )
    
@lru_cache(maxsize=256)
def get_modelform(Model, field_tuple):

    def formfield_callback(db_field, **kwargs):

        # DateField
        if db_field.get_internal_type() == "DateField":
            kwargs["widget"] = forms.DateInput(
                attrs={"type": "date"},
                format="%Y-%m-%d"
            )
            kwargs["input_formats"] = ["%Y-%m-%d"]

        # DateTimeField
        elif db_field.get_internal_type() == "DateTimeField":
            kwargs["widget"] = forms.DateTimeInput(
                attrs={"type": "datetime-local"},
                format="%Y-%m-%dT%H:%M"
            )
            kwargs["input_formats"] = ["%Y-%m-%dT%H:%M"]

        return db_field.formfield(**kwargs)

    return modelform_factory(
        Model,
        fields=list(field_tuple),
        formfield_callback=formfield_callback
    )

from django.core.exceptions import ValidationError

def apply_model_validation(form, obj):
    """
    Run model validation and attach errors properly to form.
    """
    try:
        obj.full_clean()
    except ValidationError as e:

        # Case 1: Field-specific errors
        if hasattr(e, "message_dict"):
            for field, messages in e.message_dict.items():
                for msg in messages:
                    form.add_error(field, msg)

        # Case 2: Non-field errors
        elif hasattr(e, "messages"):
            for msg in e.messages:
                form.add_error(None, msg)

        return False

    return True

# CRUD views (create / update / detail / delete)
@require_http_methods(["GET", "POST"])
@login_required
def generic_create_object(request: HttpRequest, model: str) -> HttpResponse:
    Model = get_model(model)

    if not Model:
        return HttpResponseNotFound(f"Model '{model}' not found")

    perm_codename = f"{Model._meta.app_label}.add_{Model.__name__.lower()}"
    if not request.user.has_perm(perm_codename):
        return HttpResponseForbidden("You do not have permission to create this record.")

    fieldsets, all_fieldset_fields, ordered_editable_fields = get_fieldsets_for_model_cached(model)

    # On CREATE → allow all fields (ignore visibility/editability)
    field_tuple = tuple(ordered_editable_fields)

    Form = get_modelform(Model, field_tuple)

    if request.method == "POST":
        safe_post = sanitize_post_for_model(
            request.user, Model, request.POST, ordered_editable_fields,bypass_permissions=True 
        )
        form = Form(safe_post, request.FILES)
    else:
        form = Form()
    

    User = get_user_model()
    allowed_user = get_allowed_user_queryset(request.user)

    for field in form.fields.values():
        if hasattr(field, "queryset") and getattr(field.queryset, "model", None) == User:
            field.queryset = allowed_user

    # 🔁 UPDATED BLOCK START-- Avi
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        # 🔥 MUST: apply audit logic BEFORE validation
        apply_audit_logic(obj, request, is_create=True)

        # 🔥 FIX 2: Now run validation
        is_valid = apply_model_validation(form, obj)

        if is_valid:
            obj.save()
            form.save_m2m()

            # return redirect("crm_object_detail", model=model, pk=obj.pk)
            return redirect("listview_results", model_name=model)

    return render(request, "crm/generic/generic_create.html", {
        "model_name": model,
        "title": f"Create {model}",
        "form": form,
        "fieldsets": fieldsets,
        "all_fieldset_fields": all_fieldset_fields,
    })

@login_required
@require_http_methods(["GET", "POST"])
def generic_update_object(request: HttpRequest, model: str, pk: int) -> HttpResponse:
    Model = get_model(model)
    if not Model:
        return HttpResponseNotFound("Model not found")

    # Permission check
    perm = f"{Model._meta.app_label}.change_{Model.__name__.lower()}"
    if not request.user.has_perm(perm):
        return HttpResponseForbidden("You do not have permission to update this record.")
    
    # Object access
    instance = get_visible_queryset(Model, request.user).filter(pk=pk).first()
    if not instance:
        return HttpResponseForbidden("You do not have access to this record.")

    fieldsets, all_fieldset_fields, ordered_editable_fields = get_fieldsets_for_model_cached(model)

    ordered_editable_fields = [
        f for f in ordered_editable_fields
        if is_field_visible(request.user, Model, f)
        and is_field_editable(request.user, Model, f)
    ]

    field_tuple = tuple(ordered_editable_fields)
    Form = get_modelform(Model, field_tuple)

    # Bind form
    if request.method == "POST":
        print("RAW POST:", dict(request.POST))

        safe_post = sanitize_post_for_model(
            request.user,
            Model,
            request.POST,
            ordered_editable_fields,
            instance=instance
        )

        form = Form(safe_post, request.FILES, instance=instance)
    else:
        form = Form(instance=instance) 
    

    # SAME queryset logic
    User = get_user_model()
    allowed_user = get_allowed_user_queryset(request.user)

    for field in form.fields.values():
        if hasattr(field, "queryset") and getattr(field.queryset, "model", None) == User:
            field.queryset = allowed_user

    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            obj = form.save(commit=False)
            # MUST: apply audit logic BEFORE validation
            apply_audit_logic(obj, request, is_create=False)
            # ADDED: Apply model-level validation (calls clean())
            is_valid = apply_model_validation(form, obj)

            if is_valid:
                obj.save()
                form.save_m2m()

                # return redirect("crm_object_detail", model=model, pk=obj.pk)
            return redirect("listview_results", model_name=model)
                
    return render(request, "crm/generic/generic_edit.html", {
        "model_name": model,
        "title": f"Edit {model}",
        "form": form,
        "obj": instance,
        "fieldsets": fieldsets,
    })

@require_GET
@login_required
def generic_detail_object(request: HttpRequest, model: str, pk: int) -> HttpResponse:
   
    Model = get_model(model)
    if not Model:
        return HttpResponseNotFound("Model not found")

    
    perm_codename = f"{Model._meta.app_label}.view_{Model.__name__.lower()}"
    if not request.user.has_perm(perm_codename):
        return forbidden(request, "You do not have permission to view this record.")

   
    obj = (
        get_visible_queryset(Model, request.user)
        .filter(pk=pk)
        .first()
    )
    if not obj:
        return HttpResponseForbidden("You do not have access to this record.")

   
    fieldsets, _, _ = get_fieldsets_for_model_cached(model)

   
    model_fields = {
        f.name: f
        for f in Model._meta.get_fields()
    }

    visible_fields, _ = get_accessible_fields_cached(
        request.user.pk,
        Model.__name__
    )

    rendered_fieldsets = []
    audit_fields = set()
    section_counter = 1

    for fs in fieldsets:
        rendered_fields = []

        for field_name in fs.get("fields", []):
            # Skip unknown fields
            field = model_fields.get(field_name)
            if not field:
                continue

            # Field-level visibility
            if visible_fields and field_name not in visible_fields:
                continue

            # Audit fields → separate section
            if field_name in NON_FORM_FIELDS:
                audit_fields.add(field_name)
                continue

            render_type, value = get_rendered_field(Model, obj, field_name)

            rendered_fields.append({
                "name": field_name,
                "label": field.verbose_name.title(),
                "value": value,
                "render": render_type,
            })

        if rendered_fields:
            rendered_fieldsets.append({
                "id": fs.get("id", f"section_{section_counter}"),
                "title": fs.get("title", f"Section {section_counter}"),
                "fields": rendered_fields,
            })
            section_counter += 1

    if audit_fields:
        audit_rendered = []

        for field_name in sorted(audit_fields):
            field = model_fields.get(field_name)
            label = field.verbose_name.title() if field else field_name

            render_type, value = get_rendered_field(Model, obj, field_name)

            audit_rendered.append({
                "name": field_name,
                "label": label,
                "value": value,
                "render": render_type,
            })

        rendered_fieldsets.append({
            "id": "audit_section",
            "title": "Audit Fields",
            "fields": audit_rendered,
        })

    return render(request, "crm/generic/generic_detail.html", {
        "model_name": model,
        "obj": obj,
        "users": User.objects.all(),
        "fieldsets": rendered_fieldsets,
        "LEAD_STATUS_CHOICES": LEAD_STATUS_CHOICES,
        "has_history" : hasattr(obj, "history")
    })


@require_http_methods(["GET", "POST"])
@login_required
def generic_delete_object(request: HttpRequest, model: str, pk: int) -> HttpResponse:
    Model = get_model(model)
    if not Model:
        return HttpResponseNotFound("Model not found")

    perm = f"{Model._meta.app_label}.delete_{Model.__name__.lower()}"
    if not request.user.has_perm(perm):
        return HttpResponseForbidden("You do not have permission to delete this record.")

    instance = get_visible_queryset(Model, request.user).filter(pk=pk).first()
    if not instance:
        return HttpResponseForbidden("You do not have access to this record.")

    if request.method == "POST":
        instance.delete()
        messages.success(request, f"{Model.__name__} deleted successfully.")

        listview_pk = get_default_listview_pk(model)
        return redirect("listview_results", model.lower()) if listview_pk else redirect(
            "crm_object_list", model=model
        )

    return render(request, "crm/generic/generic_delete_confirm.html", {
        "model_name": model,
        "obj": instance,
    })

def resolve_history_value(model, field_name, value):
    """
    Resolve history diff values into human-readable output.
    Correctly handles:
    - User FKs
    - Deleted users
    - Deleted related records
    - Raw strings
    """
    try:
        field = model._meta.get_field(field_name)
    except Exception:
        return str(value) if value not in ("", None) else "—"


    if field.is_relation and field.many_to_one:
        rel_model = field.remote_field.model

        # ---------- USER FK ----------
        if rel_model == User:

            # Case 1: value already string (username)
            if isinstance(value, str):
                return value

            # Case 2: value is None → deleted user
            if value is None:
                return "Deleted user"

            # Case 3: value is PK
            user = User.objects.filter(pk=value).first()
            return user.username if user else "Deleted user"

        # ---------- OTHER FK ----------
        if value is None:
            return "Deleted record"

        obj = rel_model.objects.filter(pk=value).first()
        return str(obj) if obj else "Deleted record"

    # Normal field (non-relation)
    if value in ("", None):
        return " "

    return str(value)

def resolve_field_label(model, field_name):
    """
    Returns human-readable field label for audit logs.
    Falls back safely if field does not exist.
    """
    try:
        field = model._meta.get_field(field_name)
        return field.verbose_name.title()
    except Exception:
        # fallback for non-model fields
        return field_name.replace("_", " ").title()


@login_required
def generic_object_history(request, model: str, pk: int):

    # Load model safely
    Model = get_model(model)
    if not Model:
        return HttpResponseNotFound("Model not found")

    # Object-level VIEW permission
    view_perm = f"{Model._meta.app_label}.view_{Model.__name__.lower()}"
    if not (request.user.is_superuser or request.user.has_perm(view_perm)):
        return HttpResponseForbidden("You do not have permission to view this record.")

    # Fetch object with visibility rules
    obj = get_visible_queryset(Model, request.user).filter(pk=pk).first()
    if not obj:
        return HttpResponseForbidden("You do not have access to this record.")

    # History support check
    if not hasattr(obj, "history"):
        return HttpResponseNotFound("History not available for this object.")

    # History permission
    history_perm = f"{Model._meta.app_label}.view_{Model.__name__.lower()}_history"
    if not request.user.has_perm(history_perm):
        return HttpResponseForbidden("You do not have permission to view history.")


    # Load history + attach diffs
    raw_history = list(
        obj.history
        .select_related("history_user")
        .order_by("-history_date")
    )

    history_entries = []

    for i, current in enumerate(raw_history):
        changes = []

        if i < len(raw_history) - 1:
            previous = raw_history[i + 1]
            delta = current.diff_against(previous)

            for c in delta.changes:
                changes.append({
                    "field": resolve_field_label(Model, c.field),
                    "old": resolve_history_value(Model, c.field, c.old),
                    "new": resolve_history_value(Model, c.field, c.new),
                })

        history_entries.append({
            "object": obj,
            "date": current.history_date,
            "user": current.history_user,
            "type": current.history_type,
            "reason": current.history_change_reason,
            "changes": changes,
        })

    return render(request, "crm/generic/object_history.html", {
        "model_name": model,
        "obj": obj,
        "history_entries": history_entries,
    })
