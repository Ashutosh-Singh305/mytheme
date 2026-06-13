import datetime
from warnings import filters
from django.http import HttpResponse
from crm.models import UserProfile, FieldAccessControl
import pandas as pd
from django.http import HttpResponse
from django.utils.timezone import is_aware, now
from django.db.models import Q
from django.contrib.auth import get_user_model
User = get_user_model()

def get_accessible_fields(user, model_name):
    profile = UserProfile.objects.filter(user=user).first()
    if not profile:
        return set(), set()

    field_permissions = FieldAccessControl.objects.filter(role=profile.role, model_name=model_name)
    viewable_fields = {fp.field_name for fp in field_permissions if fp.can_view}
    editable_fields = {fp.field_name for fp in field_permissions if fp.can_edit}
    return viewable_fields, editable_fields

def get_subordinate_users(user):
    # Get profile safely
    profile = UserProfile.objects.filter(user=user).select_related('branch').first()
    
    if not profile:
        return []  # No profile → no hierarchy
    
    if not profile.branch:
        return []  # No branch assigned

    userbranch = profile.branch
    subordinates = []

    def collect_subs(manager):
        reports = UserProfile.objects.filter(
            manager=manager,
            branch=userbranch
        ).select_related('user')

        for r in reports:
            subordinates.append(r.user)
            collect_subs(r.user)

    collect_subs(user)
    return subordinates


# Edited On 26-03-2026: Added branch-based filtering for non-admin users by Ashutosh Kumar
def get_visible_queryset(model, user, owner_field="assigned_to"):
    profile = UserProfile.objects.filter(user=user).first()

    if profile and profile.role == "Admin":
        return model.objects.all()
    
    

    subordinate_users = get_subordinate_users(user)
    allowed_users = [user] + subordinate_users

    return model.objects.filter(**{f"{owner_field}__in": allowed_users})

# TO get user for dropdown
# def get_allowed_user_queryset(user):
#     profile = UserProfile.objects.filter(user=user).first()

#     if profile and profile.role == "Admin":
#         return User.objects.all()

#     subordinates = get_subordinate_users(user)
#     allowed_users = [user] + subordinates
#     allowed_ids = set()
    
#     for u in allowed_users:
#         allowed_ids.add(u.id)

#     return User.objects.filter(id__in=allowed_ids)

def get_allowed_user_queryset(user):
    profile = getattr(user, "userprofile", None)

    # Admin → all active users
    if profile and profile.role == "Admin":
        return User.objects.filter(is_active=True)

    # If no profile OR no branch → only self
    if not profile or not profile.branch:
        return User.objects.filter(id=user.id)

    # Same branch + active users
    return User.objects.filter(
        is_active=True,
        userprofile__branch=profile.branch
    )


def get_lead_allowed_user_queryset(user, field_name=None):
    profile = getattr(user, "userprofile", None)

    role_map = {
        'sm': ['SM', 'Business Manager', 'BH'],
        'team_lead': ['TL', 'Business Manager', 'SM', 'BH'],
        'business_manager': ['Business Manager', 'BH'],
        'business_head': ['BH'],
        'recruiter': ['Hr Executive']
    }

    # Base queryset (active users only)
    qs = User.objects.filter(
        is_active=True,
        userprofile__isnull=False
    ).select_related('userprofile')

    # Apply role_map (ALWAYS)
    if field_name in role_map:
        qs = qs.filter(userprofile__role__in=role_map[field_name])

    # ADMIN → all active users (NO branch filter)
    if profile and profile.role == "Admin":
        return qs.order_by('first_name', 'last_name')

    #  No profile OR no branch → only self
    if not profile or not profile.branch:
        return User.objects.filter(id=user.id)

    #  Others → same branch only
    qs = qs.filter(userprofile__branch=profile.branch)

    return qs.order_by('first_name', 'last_name')

    


def get_model_diff(old, new):
    diffs = {}
    for field in old._meta.fields:
        name = field.name

        if name.startswith('history_') or name in ['id']:
            continue

        old_val = getattr(old, name, None)
        new_val = getattr(new, name, None)

        # Normalize for comparison
        old_val_str = str(old_val).strip() if old_val is not None else ''
        new_val_str = str(new_val).strip() if new_val is not None else ''

        if old_val_str != new_val_str:
            verbose_name = getattr(field, 'verbose_name', name).capitalize()
            diffs[verbose_name] = (old_val, new_val)

    return diffs

from io import BytesIO
import re

# 🔴 Excel-safe sanitizer
ILLEGAL_CHARACTERS_RE = re.compile(r'[\x00-\x08\x0B-\x0C\x0E-\x1F]')

def clean_excel_value(value):
    if isinstance(value, str):
        return ILLEGAL_CHARACTERS_RE.sub('', value)
    return value


def export_as_excel_generic(modeladmin, request, queryset):
    if not request.user.has_perm("crm.can_export_data"):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("You do not have permission to export data.")

    model = queryset.model
    opts = model._meta

    fields = [
        field for field in opts.get_fields()
        if not (
            field.many_to_many or
            field.one_to_many or
            (field.auto_created and not field.concrete)
        )
    ]

    data = []

    for obj in queryset.iterator():
        row = {}

        for field in fields:
            label = field.verbose_name.title() if hasattr(field, "verbose_name") else field.name

            try:
                value = getattr(obj, field.name)

                if field.is_relation and value is not None:
                    value = str(value)

                elif field.choices:
                    value = getattr(obj, f"get_{field.name}_display")()

                elif isinstance(value, datetime.datetime):
                    if is_aware(value):
                        value = value.astimezone(None).replace(tzinfo=None)
                    value = value.strftime('%d-%m-%Y %H:%M:%S')

                elif isinstance(value, datetime.date):
                    value = value.strftime('%d-%m-%Y')

                # 🔴 CRITICAL FIX
                value = clean_excel_value(value)

                row[label] = value

            except Exception:
                row[label] = ""

        data.append(row)

    df = pd.DataFrame(data)

    # 🔴 EXTRA SAFETY (important)
    if not df.empty:
        df = df.applymap(clean_excel_value)

    buffer = BytesIO()

    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name=opts.verbose_name_plural.title())

    buffer.seek(0)

    filename = f"{model.__name__.lower()}_export_{datetime.datetime.now().strftime('%d-%m-%Y_%H-%M-%S')}.xlsx"

    response = HttpResponse(
        buffer,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

    response['Content-Disposition'] = f'attachment; filename={filename}'

    return response


export_as_excel_generic.short_description = "Export Select Data"

############ Common audit logic for Admin + CRUD ############
def apply_audit_logic(obj, request, is_create=False):
    """
    🔥 Shared logic for Admin + CRUD
    """

    if hasattr(obj, "assigned_to") and not obj.assigned_to:
        obj.assigned_to = request.user

    if is_create:
        if hasattr(obj, "created_by") and not obj.created_by:
            obj.created_by = request.user

    if hasattr(obj, "modified_by"):
        obj.modified_by = request.user

    # 🔥 IMPORTANT: handle bulk update issue
    if hasattr(obj, "modified_at"):
        obj.modified_at = now()