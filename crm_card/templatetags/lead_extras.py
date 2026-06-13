from django import template
register = template.Library()

# Show full name for User objects, fallback to username
from django.contrib.auth import get_user_model
User = get_user_model()


@register.filter
def user_display(obj):
    if hasattr(obj, 'get_full_name') and callable(obj.get_full_name):
        full_name = obj.get_full_name()
        if full_name:
            return full_name
    if hasattr(obj, 'username'):
        return obj.username
    return str(obj)

@register.filter(name='getattr')
def get_attr(obj, attr):
    # Try attribute, then dict key, then method/property
    try:
        # Try attribute access
        value = getattr(obj, attr, None)
        if callable(value):
            try:
                value = value()
            except Exception:
                return ''
        # If value is a model instance, return its string representation
        from django.db.models import Model
        if isinstance(value, Model):
            return str(value)
        return value
    except Exception:
        pass
    # Try dict access
    if isinstance(obj, dict) and attr in obj:
        return obj[attr]
    # Try __getitem__ for objects that support it
    try:
        return obj[attr]
    except Exception:
        pass
    # Debug: Uncomment the next line to see what is missing
    # return f"[Missing: {attr}]"
    return ''


# Add get_item filter for dictionary key access
@register.filter
def get_item(dictionary, key):
    if isinstance(dictionary, dict):
        return dictionary.get(key, '')
    return ''


# Add replace filter for string replacement in templates

@register.filter
def replace(value, args):
    """Replaces all occurrences of first arg with second arg in the string. Usage: {{ value|replace:'_ ' }}"""
    try:
        old, new = args.split(' ')
        return str(value).replace(old, new)
    except Exception:
        return value


# List view config for custom lead list view (not admin)
list_display = (
    'id','modified_at','dos', 'sm', 'team_lead', 'tele_sales_executive',
    'name','application_no', 'location', 'monthly_salary', 'lender_name',
    'require_loan_amount', 'login_amount', 'net_disbursed', 'status'
)

'''
previously used     -   Currently used
sales_manager_name  -    sm
team_leader_name    -    team_lead
tele_sales_exec_name-    tele_sales_executive
'''
list_filter = [
    'mobile_number', 'tele_sales_executive', 'team_lead','sm','channel_name','lender_name', 'status'
]

search_fields = [
    'name', 'mobile_number', 'email', 'pan', 'company_name','application_no'
]

# ----------------------------------------------------------------------
#   NEW FILTERS ADDED FOR FIELDSET-BASED AUTO TEMPLATE
# ----------------------------------------------------------------------

@register.filter
def get_verbose_name(obj, field_name):
    """
    Return readable label for model field.
    """
    try:
        field = obj._meta.get_field(field_name)
        return field.verbose_name.title()
    except Exception:
        return field_name.replace('_', ' ').title()


@register.filter
def get_field_value(obj, field_name):
    """
    Safely returns value for any field:
    - Uses get_FIELD_display() for choices.
    - Formats datetime/date.
    - Returns FK string.
    - Supports properties & callable no-arg methods.
    """
    if not hasattr(obj, field_name):
        return ""

    attr = getattr(obj, field_name)

    # If choice field, use get_<field>_display()
    display_method = f"get_{field_name}_display"
    if hasattr(obj, display_method):
        try:
            return getattr(obj, display_method)()
        except Exception:
            pass

    # If callable (property or method)
    if callable(attr):
        try:
            return attr()
        except Exception:
            return ""

    # Format date/datetime
    import datetime
    if isinstance(attr, (datetime.datetime, datetime.date)):
        try:
            return attr.strftime("%d-%m-%Y")
        except Exception:
            return str(attr)

    # For queryset/list — join items
    from django.db.models import QuerySet
    if isinstance(attr, (QuerySet, list, tuple)):
        return ", ".join(str(x) for x in attr)

    # None → empty
    if attr is None:
        return ""

    return str(attr)

@register.filter
def is_list(value):
    return isinstance(value, (list, tuple))

