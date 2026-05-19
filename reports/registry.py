# reports/registry.py
from __future__ import annotations
from typing import List, Optional, Dict
from django.apps import apps
from django.db import models as djm

# Apps we will ignore when listing reportable models
IGNORE_APP_PREFIXES = (
    "django.",         # admin, auth, contenttypes, sessions, messages, staticfiles
    "rest_framework",  # if present
    "allauth", "social_", "axes",  # common third-party auth/logging
)

# If a model (class) inherits your CRM AuditModel, we consider it "ownable"
# and use assigned_to for row-level visibility.
def _inherits_audit_model(model_cls) -> bool:
    try:
        from crm.models import AuditModel  # your base
        return issubclass(model_cls, AuditModel)
    except Exception:
        # If crm not available or circular import, fail closed
        return False

def list_models() -> List[str]:
    """
    Return all *business* models (skip Django/system apps, abstract/proxy/unmanaged).
    """
    out: List[str] = []
    for config in apps.get_app_configs():
        if config.name.startswith(IGNORE_APP_PREFIXES):
            continue
        for m in config.get_models():
            # Skip abstract/proxy/unmanaged
            if getattr(m._meta, "abstract", False):
                continue
            if getattr(m._meta, "proxy", False):
                continue
            if getattr(m._meta, "managed", True) is False:
                continue
            out.append(f"{m._meta.app_label}.{m.__name__}")
    return sorted(out)

def list_fields(model_label: str) -> List[str]:
    """
    Expose concrete fields + simple FK readable fields.
    """
    app_label, model_name = model_label.split(".")
    m = apps.get_model(app_label, model_name)
    out: List[str] = []
    for f in m._meta.get_fields():
        if getattr(f, "concrete", False) and not f.many_to_many and not f.one_to_many:
            out.append(f.name)
        # For FK, add a single readable hop if present
        if getattr(f, "many_to_one", False) and getattr(f, "remote_field", None):
            rel = f.remote_field.model
            for cand in ("name", "username", "title"):
                if hasattr(rel, cand):
                    out.append(f"{f.name}__{cand}")
                    break
    return out

def owner_field(model_label: str) -> Optional[str]:
    """
    If model inherits AuditModel, use 'assigned_to'. Else None.
    """
    app_label, model_name = model_label.split(".")
    m = apps.get_model(app_label, model_name)
    return "assigned_to" if _inherits_audit_model(m) else None



def apply_visibility(qs, user, model_label: str):
    """
    Call your crm.utils.get_visible_queryset with the *model* (not qs),
    but support both signatures just in case.
    """
    try:
        from crm.utils import get_visible_queryset
    except Exception:
        return qs

    # resolve model class from "app_label.ModelName"
    app_label, model_name = model_label.split(".")
    Model = apps.get_model(app_label, model_name)

    ofield = owner_field(model_label)

    # Prefer calling with model=... (your impl needs this)
    try:
        return get_visible_queryset(model=Model, user=user, owner_field=ofield) if ofield \
               else get_visible_queryset(model=Model, user=user)
    except TypeError:
        # Fallbacks if the helper has a different signature
        try:
            return get_visible_queryset(Model, user=user, owner_field=ofield) if ofield \
                   else get_visible_queryset(Model, user=user)
        except TypeError:
            # Last resort: pass the queryset (older variants)
            return get_visible_queryset(qs, user=user, owner_field=ofield) if ofield \
                   else get_visible_queryset(qs, user=user)

