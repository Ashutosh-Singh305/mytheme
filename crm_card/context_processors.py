from django.apps import apps
from django.db import models

from crm.models import ListView, ListViewField


# -----------------------------------
# GLOBAL LISTVIEW CONFIG
# -----------------------------------

EXCLUDED_LISTVIEW_FIELDS = {
    # System fields
    "password",
    "groups",
    "user_permissions",
    "last_login",

    # Heavy text fields
    "description",
    "features",
    "eligibility_criteria",
    "remarks",
    "notes",
    "feedback",

    # Audit/history
    "history",

    # File/Image fields
    "photo",
    "resume",
    "file",
    "image",
    "product_image",
    "product_icon",
    "icon",

    # Internal fields
    "is_superuser",
    "is_staff",
    "is_active",
}


ALLOWED_FIELD_TYPES = (
    models.CharField,
    models.EmailField,
    models.IntegerField,
    models.DecimalField,
    models.BooleanField,
    models.DateField,
    models.DateTimeField,
    models.ForeignKey,
)


PRIORITY_FIELDS = [
    "id",
    "name",
    "full_name",
    "title",
    "mobile",
    "mobile_number",
    "phone",
    "email",
    "status",
    "assigned_to",
    "created_date",
    "created_at",
]


MAX_DEFAULT_FIELDS = 10


# -----------------------------------
# SMART FIELD DETECTOR
# -----------------------------------

def get_smart_listview_fields(model):

    fields = []

    for field in model._meta.get_fields():

        # Skip reverse relations
        if field.auto_created:
            continue

        # Skip M2M
        if field.many_to_many:
            continue

        # Skip excluded names
        if field.name in EXCLUDED_LISTVIEW_FIELDS:
            continue

        # Skip unsupported field types
        if not isinstance(field, ALLOWED_FIELD_TYPES):
            continue

        fields.append(field)

    # -----------------------------------
    # PRIORITY SORTING
    # -----------------------------------

    def field_priority(field):

        try:
            return PRIORITY_FIELDS.index(field.name)
        except ValueError:
            return 999

    fields.sort(key=field_priority)

    # Limit columns
    fields = fields[:MAX_DEFAULT_FIELDS]

    return [f.name for f in fields]


# -----------------------------------
# MAIN FUNCTION
# -----------------------------------

def get_or_create_default_listview(model_name, user=None):

    # Existing default
    default_lv = ListView.objects.filter(
        object_name=model_name,
        is_default=True
    ).first()

    if default_lv:
        return default_lv

    # Existing non-default
    other_lv = ListView.objects.filter(
        object_name=model_name
    ).first()

    if other_lv:
        other_lv.is_default = True
        other_lv.save(update_fields=["is_default"])
        return other_lv

    # -----------------------------------
    # CREATE NEW DEFAULT LISTVIEW
    # -----------------------------------

    Model = apps.get_model("crm", model_name)

    lv = ListView.objects.create(
        object_name=model_name,
        name=f"All {model_name}",
        visibility="public",
        is_default=True,
        created_by=user if user else None,
    )

    # -----------------------------------
    # SMART FIELD GENERATION
    # -----------------------------------

    smart_fields = get_smart_listview_fields(Model)

    for i, field_name in enumerate(smart_fields):

        ListViewField.objects.create(
            list_view=lv,
            field_name=field_name,
            order=i
        )

    return lv