from django.contrib import admin
from django.utils.timezone import now
from crm.utils import get_allowed_user_queryset, get_visible_queryset
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from django.contrib.admin import SimpleListFilter
import datetime
from django.db.models import DateField, DateTimeField
from crm.utils import apply_audit_logic


class BaseAuditAdmin(admin.ModelAdmin):
    readonly_audit_fields = ['created_by', 'created_date', 'modified_by', 'modified_at']
    audit_fields = ['assigned_to'] + readonly_audit_fields
    readonly_fields = readonly_audit_fields

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return get_visible_queryset(self.model, request.user, owner_field="assigned_to")

    def get_fieldsets(self, request, obj=None):
        if self.fieldsets:
            return super().get_fieldsets(request, obj)

        fields = [
            f.name for f in self.model._meta.fields
            if f.name not in self.audit_fields and f.editable and f.name != 'id'
        ]

        return [
            (None, {'fields': fields}),
            ('Audit Info', {'fields': self.audit_fields, 'classes': ('wide',)}),
        ]

    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        
        #Apply hierarchy + branch filter
        # if db_field.remote_field.model == User:
        #     kwargs["queryset"] = get_allowed_user_queryset(request.user)
        
        formfield = super().formfield_for_foreignkey(db_field, request, **kwargs)
        
        if db_field.remote_field.model == User:
            formfield.label_from_instance = lambda obj: f"{obj.get_full_name()} ({obj.username})"
        
        return formfield
    
    def save_model(self, request, obj, form, change):

        apply_audit_logic(obj, request, is_create=not obj.pk)

        super().save_model(request, obj, form, change)
   

# --------------------------------
# Generic reusable DateRangeFilter
# --------------------------------
class DateRangeFilter(SimpleListFilter):
    title = _('Date Range')
    parameter_name = 'date_range'

    def __init__(self, request, params, model, model_admin):
        if not hasattr(self, 'parameter_name') or not self.parameter_name:
            self.parameter_name = 'date_range'
        # Get field type
        try:
            field_object = model._meta.get_field(self.parameter_name)
            self.is_datefield = isinstance(field_object, DateField) and not isinstance(field_object, DateTimeField)
        except:
            self.is_datefield = False
        super().__init__(request, params, model, model_admin)

    def lookups(self, request, model_admin):
        return (
            ('today', _('Today')),
            ('yesterday', _('Yesterday')),   # ✅ Added here
            ('7_days', _('Last 7 days')),
            ('30_days', _('Last 30 days')),
            ('this_month', _('This month')),
            ('last_month', _('Last month')),
        )

    def queryset(self, request, queryset):
        value = self.value()
        today = datetime.date.today()

        if not self.parameter_name:
            return queryset

        # Decide field lookup based on type
        if self.is_datefield:
            field = f"{self.parameter_name}"
        else:
            field = f"{self.parameter_name}__date"

        if value == 'today':
            return queryset.filter(**{field: today})
        elif value == 'yesterday':  # ✅ Added condition
            yesterday = today - datetime.timedelta(days=1)
            return queryset.filter(**{field: yesterday})
        elif value == '7_days':
            start = today - datetime.timedelta(days=7)
            return queryset.filter(**{f"{field}__gte": start})
        elif value == '30_days':
            start = today - datetime.timedelta(days=30)
            return queryset.filter(**{f"{field}__gte": start})
        elif value == 'this_month':
            first_day = today.replace(day=1)
            return queryset.filter(**{f"{field}__gte": first_day, f"{field}__lte": today})
        elif value == 'last_month':
            first_day_current = today.replace(day=1)
            last_day_last = first_day_current - datetime.timedelta(days=1)
            first_day_last = last_day_last.replace(day=1)
            return queryset.filter(**{f"{field}__range": (first_day_last, last_day_last)})
        return queryset


# --------------------------------
# Specific re-usable subclasses for Datefield Filters
# --------------------------------

class CreatedDateRangeFilter(DateRangeFilter):
    title = _('Created Date')
    parameter_name = 'created_date'

class ModifiedDateRangeFilter(DateRangeFilter):
    title = _('Modified Date')
    parameter_name = 'modified_at'

class CallingDateRangeFilter(DateRangeFilter):
    title = _('Calling Date')
    parameter_name = 'calling_date'

class InterviewDateRangeFilter(DateRangeFilter):
    title = _('Interview Date')
    parameter_name = 'interview_date'

class TrainingDateRangeFilter(DateRangeFilter):
    title = _('Training Date')
    parameter_name = 'training_date'

class ActualJoiningDateRangeFilter(DateRangeFilter):
    title = _('Actual Joining Date')
    parameter_name = 'actual_joining_date'

class DODRangeFilter(DateRangeFilter):
    title = _('Date Of Disbursement')
    parameter_name = 'dod'

class DOLRangeFilter(DateRangeFilter):
    title = _('Date Of Login')
    parameter_name = 'dol'

class DOSRangeFilter(DateRangeFilter):
    title = _('DOS')
    parameter_name = 'dos'