from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.urls import reverse
from .models import *
from .admin_base import *
from .admin_forms import RoleBasedAccessForm, LeadFollowUpAdminForm
from django.http import HttpResponse
from django.utils.html import format_html
from simple_history.admin import SimpleHistoryAdmin
from crm.utils import export_as_excel_generic
from django.contrib.admin import SimpleListFilter
from django.utils.translation import gettext_lazy as _
from django.contrib.admin import DateFieldListFilter
from crm.choices import LEAD_STATUS_CHOICES
# NEW: needed to read preserved filters when clicking "Add" from changelist
from urllib.parse import parse_qsl

admin.site.site_header = "Welcome to APIS CRM Portal"
admin.site.site_title = "APIS Finserv CRM Admin"
admin.site.index_title = "Welcome to APIS CRM Portal"
admin.site.disable_action('delete_selected')

from django.utils.translation import gettext_lazy as _
from django.contrib.admin import SimpleListFilter
import datetime

# Custom date range filters for Leadfollowup model by Ashutosh
from datetime import datetime, date, timedelta
from django.utils.timezone import make_aware, get_current_timezone


class LeadAdminForm(RoleBasedAccessForm):
    class Meta:
        model = Lead
        fields = '__all__'
        
    def clean(self):
        cleaned_data = super().clean()

        status = cleaned_data.get("status")

        if status == "disbursed":
            readable_status = dict(LEAD_STATUS_CHOICES).get(status, status)

            for field_name, field in self.fields.items():
                value = cleaned_data.get(field_name)

                if value in (None, "", []):
                    self.add_error(
                        field_name,
                        f"{field.label or field_name} is required when status is {readable_status}."
                    )

        return cleaned_data

@admin.register(Lead)
class LeadAdmin(SimpleHistoryAdmin,BaseAuditAdmin):
    form = LeadAdminForm
    # ✅ use a custom template (adds "View Follow-ups" button)
    change_form_template = "admin/crm/lead/change_form.html"
    class Media:
        js = ('admin/js/branch_name.js',)

    autocomplete = [
        'assigned_to',
        'team_lead',
        'backend_executive_user',
        'business_head',
        'business_manager',
        'tele_sales_executive',
        'sm',
    ]

    list_display = (
        'id','modified_at','dos', 'sales_manager_name', 'team_leader_name', 'tele_sales_exec_name',
        'name','application_no', 'location', 'monthly_salary', 'lender_name',
        'require_loan_amount', 'login_amount', 'net_disbursed', 'status'
    )

    def sales_manager_name(self, obj):
        return obj.sm.get_full_name() if obj.sm else ""
    sales_manager_name.short_description = 'Sales Manager'
    sales_manager_name.admin_order_field = 'sm__first_name'  # or 'sm__last_name'

    def team_leader_name(self, obj):
        return obj.team_lead.get_full_name() if obj.team_lead else ""
    team_leader_name.short_description = 'Team Leader'
    team_leader_name.admin_order_field = 'team_lead__first_name'

    def tele_sales_exec_name(self, obj):
        return obj.tele_sales_executive.get_full_name() if obj.tele_sales_executive else ""
    tele_sales_exec_name.short_description = 'Tele Sales Executive'
    tele_sales_exec_name.admin_order_field = 'tele_sales_executive__first_name'

    list_display_links = ['name','id']  # Make username clickable
    list_filter = (CreatedDateRangeFilter,ModifiedDateRangeFilter, 'mobile_number', 'tele_sales_executive', 'team_lead','sm','channel_name','lender_name', 'status',DODRangeFilter,DOLRangeFilter,DOSRangeFilter)
    search_fields = ('name', 'mobile_number', 'email', 'pan', 'company_name','application_no')
    #actions = ['export_as_excel']
    actions = [export_as_excel_generic]

    fieldsets = (
        ('Personal Details', {
            'classes': ('wide',),
            'fields': (
                'name',
                'mobile_number',
                'dob',
                'gender',
                'pan',
                'present_address',
                'location',
                'pincode',
                'father_name',
                'mother_name',
                'email',
                'adhar_number',
            )
        }),

        ('Employment Details', {
            'classes': ('wide',),
            'fields': (
                'employment_type',          # salaried / self employed
                'company_name',             # company / business name
                'monthly_salary',           # monthly income
                'office_address',
                'office_email',
            )
        }),

        ('Card Details', {
            'classes': ('wide',),
            'fields': (
                'existing_cc_details',      # existing card name + limit
                'lender_name',
                'lead_source',
                'status',
                'description',
            )
        }),
        ('Assignment & Meta', {
            'classes': ('wide',),
            'fields': (
                'team_lead',
                'tele_sales_executive', 
            )
        }),

        ('Audit Info', {
            'classes': ('collapse',),
            'fields': (
                'assigned_to', 'created_by', 'created_date', 'modified_by', 'modified_at'
            )
        }),
    )

    def get_form(self, request, obj=None, **kwargs):
        form_class = super().get_form(request, obj, **kwargs)

        class FormWithUser(form_class):
            def __init__(self, *args, **fkwargs):
                fkwargs['user'] = request.user
                super().__init__(*args, **fkwargs)

        return FormWithUser

    def formfield_for_foreignkey(self, db_field, request, **kwargs):

        # Lead field -> allowed role codes
        role_map = {
            'sm': ['SM', 'BM', 'BH'],
            'team_lead': ['TL', 'SM', 'BM', 'BH'],
            'business_manager': ['BM', 'BH'],
            'business_head': ['BH'],
        }

        if db_field.name in role_map:

            allowed_roles = role_map.get(
                db_field.name,
                []
            )

            kwargs['queryset'] = (

                User.objects

                .filter(
                    is_active=True,
                    userprofile__isnull=False,
                    userprofile__role__code__in=allowed_roles
                )

                .select_related(
                    'userprofile',
                    'userprofile__role',
                    'userprofile__branch'
                )

                .distinct()

                .order_by(
                    'first_name',
                    'last_name'
                )
            )

        return super().formfield_for_foreignkey(
            db_field,
            request,
            **kwargs
        )

    # ✅ Provide a "View Follow-ups" URL filtered to this lead
    def change_view(self, request, object_id, form_url='', extra_context=None):
        if extra_context is None:
            extra_context = {}
        changelist_url = reverse('admin:crm_leadfollowup_changelist')
        # exact filter on lead id; admin will preserve it when clicking "Add"
        extra_context['view_followups_url'] = f"{changelist_url}?lead__id__exact={object_id}"
        return super().change_view(request, object_id, form_url, extra_context)


@admin.register(LoanProduct)
class LoanProductAdmin(BaseAuditAdmin):
    list_display = (
        'id', 'name', 'bank', 'interest_rate',
        'tenure_months', 'max_amount', 'min_salary_required'
    )
    list_filter = ('bank',)
    search_fields = ('name',)


@admin.register(Document)
class DocumentAdmin(BaseAuditAdmin):
    list_display = (
        'id', 'lead', 'document_type', 'uploaded_at', 'created_by'
    )
    list_filter = ('document_type',)
    search_fields = ('lead__name', 'document_type')
    
    
# Custom date range filters for Leadfollowup model by Ashutosh
class FollowUpDateFilter(admin.SimpleListFilter):
    title = 'Follow Up Date'  # Filter title in admin
    parameter_name = 'follow_up_date'  # URL query param

    def lookups(self, request, model_admin):
        return (
            ('today', 'Today'),
            ('past_7', 'Past 7 days'),
            ('this_month', 'This month'),
            ('this_year', 'This year'),  # ✅ new option
        )

    def queryset(self, request, queryset):
        tz = get_current_timezone()
        today = date.today()

        if self.value() == 'today':
            start = make_aware(datetime.combine(today, datetime.min.time()), tz)
            end = make_aware(datetime.combine(today, datetime.max.time()), tz)
            return queryset.filter(follow_up_date__range=(start, end))

        if self.value() == 'past_7':
            start = make_aware(datetime.combine(today - timedelta(days=7), datetime.min.time()), tz)
            end = make_aware(datetime.combine(today, datetime.max.time()), tz)
            return queryset.filter(follow_up_date__range=(start, end))

        if self.value() == 'this_month':
            start = make_aware(datetime.combine(today.replace(day=1), datetime.min.time()), tz)
            # last day of the month
            if today.month == 12:
                last_day = date(today.year, 12, 31)
            else:
                last_day = date(today.year, today.month + 1, 1) - timedelta(days=1)
            end = make_aware(datetime.combine(last_day, datetime.max.time()), tz)
            return queryset.filter(follow_up_date__range=(start, end))

        if self.value() == 'this_year':
            start = make_aware(datetime.combine(date(today.year, 1, 1), datetime.min.time()), tz)
            end = make_aware(datetime.combine(date(today.year, 12, 31), datetime.max.time()), tz)
            return queryset.filter(follow_up_date__range=(start, end))

        return queryset



@admin.register(LeadFollowUp)
class LeadFollowUpAdmin(BaseAuditAdmin):
    form = LeadFollowUpAdminForm

     # 👉 make the Lead column a link to the Lead change page
    def lead_link(self, obj):
        url = reverse('admin:crm_lead_change', args=[obj.lead_id])
        # shows "Lead Name (mobile)" exactly as in the lookup label
        label = f"{obj.lead.name}"
        return format_html('<a href="{}">{}</a>', url, label)
    lead_link.short_description = "Lead"
    lead_link.admin_order_field = 'lead__name'

    list_display = (
        'id', 'lead_link', 'user','note', 'follow_up_date', 'created_date'
    )
           
    
    list_filter = ('lead', FollowUpDateFilter, 'user')
    search_fields = ('lead__name', 'note')
    list_display_links = ['id']  # Make username clickable

    # ✅ Pre-populate from:
    #   1) direct querystring (?lead=&user=)
    #   2) preserved changelist filters (_changelist_filters), e.g., lead__id__exact=123
    def get_changeform_initial_data(self, request):
        data = super().get_changeform_initial_data(request)

        # direct params (if someone links /add/?lead=..&user=..)
        lead_id_direct = request.GET.get('lead')
        user_id_direct = request.GET.get('user')

        # preserved filters from changelist "Add" button
        preserved = request.GET.get('_changelist_filters')
        lead_from_filter = None
        if preserved:
            params = dict(parse_qsl(preserved))
            # support both exact-by-id and generic 'lead' param
            lead_from_filter = params.get('lead__id__exact') or params.get('lead')

        # choose the best available source
        if lead_id_direct or lead_from_filter:
            data['lead'] = lead_id_direct or lead_from_filter

        data['user'] = user_id_direct or request.user.pk
        return data

    def get_form(self, request, obj=None, **kwargs):
        base = super().get_form(request, obj, **kwargs)
        # Inject request.user so the form can filter the Lead queryset
        class Form(base):
            def __init__(self, *a, **k):
                k['user'] = request.user
                super().__init__(*a, **k)
        return Form


@admin.register(LoanApplication)
class LoanApplicationAdmin(BaseAuditAdmin):
    list_display = (
        'id', 'lead', 'product', 'loan_amount', 'tenure',
        'interest_rate', 'emi', 'status', 'submitted_at',
        'approved_at', 'disbursed_at'
    )
    list_filter = ('status', 'product')
    search_fields = ('lead__name', 'product__name')


@admin.register(BankFeedback)
class BankFeedbackAdmin(BaseAuditAdmin):
    list_display = (
        'id', 'application', 'status', 'received_at', 'created_by'
    )
    list_filter = ('status',)
    search_fields = ('application__lead__name', 'feedback')

@admin.register(Bank)
class BankAdmin(BaseAuditAdmin):
    list_display = ['id','name', 'code', 'contact_person', 'status']
    actions = [export_as_excel_generic]

@admin.register(UserProfile)
class UserProfileAdmin(BaseAuditAdmin):
    list_display = ['id', 'username', 'emp_code', 'role','user_status','branch']
    search_fields = ('emp_code', 'user__username',)
    list_display_links = ['username']  # Make username clickable

    def username(self, obj):
        return obj.user.username
    username.admin_order_field = 'user__username'  # allow column sorting
    username.short_description = 'Username'

    @admin.display(boolean=True, ordering='user__is_active', description='Active')
    def user_status(self, obj):
        return obj.user.is_active
    
"""
@admin.register(FieldAccessControl)
class FieldAccessControlAdmin(BaseAuditAdmin):
    list_display = ['role','model_name','field_name','can_view','can_edit']
"""
#admin.site.register(Contact)
@admin.register(CandidateOnboarding)
class CandidateOnboardingAdmin(BaseAuditAdmin):
    list_display = ('id','employee_code','full_name','phone','source','candidate_area', 'applied_for','calling_date', 'candidate_status','interview_date','interview_status',"training_date", "training_status",'actual_joining_date','employment_status')
    search_fields = ('full_name', 'email', 'phone', 'recruiter__username', 'recruiter_feedback','candidate_area')
    list_filter = ('source', 'applied_for', 'candidate_status',CallingDateRangeFilter,InterviewDateRangeFilter,'interview_status',"training_status",TrainingDateRangeFilter,ActualJoiningDateRangeFilter,'employment_status','candidate_area')
    list_display_links =['id','full_name']
    #autocomplete_fields = ['interviewer', 'reporting_manager', 'recruiter']
    actions = [export_as_excel_generic]
    #readonly_fields = ('photo_preview', 'resume_link')  # for detail view

    def photo_preview(self, obj):
        if obj.photo:
            return format_html('<img src="{}" width="80" height="80" style="object-fit: cover;" />', obj.photo.url)
        return "No Photo"
    photo_preview.short_description = "Photo"

    def resume_link(self, obj):
        if obj.resume:
            return format_html('<a href="{}" target="_blank">Download</a>', obj.resume.url)
        return "No Resume"
    resume_link.short_description = "Resume"
    fieldsets = (
        ("Candidate Information", {
            "fields": (
                "full_name", "phone", "alternate_number", "email",
                "gender", "date_of_birth", "qualification", "experience","relevant_exp",
                "previous_company", "previous_designation", "current_salary", "expected_salary",
                 "industry", "blood_group",
                "birth_place", "father_name", "mother_name", "adhar_number","resume","photo"
            )
        }),
        ("Recruiter / Interview Details", {
            "fields": (
                "source","applied_on","applied_for", "candidate_city", "candidate_area","recruiter", "recruiter_feedback",
                "calling_date", "candidate_status", "interview_date", "interviewer",
                "interview_status", "interview_feedback"
            )
        }),
        ("Offer & Joining Details", {
            "fields": (
                "expected_joining_date", "hired_on_salary", "designation", "actual_joining_date",
                "employee_code","reporting_manager", "department","training_date", "training_status","training_feedback",
            )
        }),
        ("Emergency Contact / Address", {
            "fields": (
                "current_address", "permanent_address", "emergency_contact_name", "emergency_contact_number",
                "relationship_with_employee", "local_ref_name", "local_ref_number", "local_ref_relationship"
            )
        }),
        ("Employment Status", {
            "fields": (
                "employment_status", "resignation_date", "last_working_day", "reason_for_resignation", "remarks"
            )
        }),
        ('Audit Info', {
            'classes': ('collapse',),
            'fields': (
                'assigned_to', 'created_by', 'created_date', 'modified_by', 'modified_at'
            )
        }),
    
    )


@admin.register(GlobalPermissions)
class GlobalPermissionsAdmin(admin.ModelAdmin):
    def has_module_permission(self, request):
        return False  # Hide the model section from sidebar

# Added by Ashu
@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'date')
    search_fields = ('name', 'email', 'phone')
    list_filter = ('date',)
    ordering = ('-date',)
    readonly_fields = ('date',)


# product related fields by Ashutosh
@admin.register(ProductCategory)
class ProductCategoryAdmin(BaseAuditAdmin):
    list_display = ('name', 'is_active', 'created_date', 'modified_at')
    search_fields = ('name',)
    list_filter = ('is_active',)

@admin.register(Product)
class ProductAdmin(BaseAuditAdmin):
    list_display = ('name', 'product_category', 'is_active','is_index')
    search_fields = ('name', 'code')
    list_filter = ('product_category', 'is_active')
    autocomplete_fields = ['product_category']  # Optional for better FK selection


@admin.register(Branch)
class BranchAdmin(BaseAuditAdmin):
    list_display = ('id','name','code', 'city', 'state','gstin', 'mobile')
    search_fields = ('name', 'contact_person')
    list_filter = ('state',)
    readonly_fields = ('created_by', 'created_date', 'modified_by', 'modified_at','code',)
    list_display_links = ['name','id']  
    fieldsets = (
        ('Basic Info', {
            'fields': ('name', 'code', 'gstin', 'isActive')
        }),
        ('Address', {
            'fields': ('address', 'city', 'state', 'pincode')
        }),
        ('Contact Details', {
            'fields': ('branch_head','mobile', 'email',)
        }),
        ('Audit Info', {
            'classes': ('collapse',),
            'fields': (
                'assigned_to', 'created_by', 'created_date', 'modified_by', 'modified_at'
            )
        }),
    )

@admin.register(IPRange)
class IPRangeAdmin(admin.ModelAdmin):
    list_display = ("start_ip", "end_ip", "is_active")
# admin.site.register(Role)
# admin.site.register(ListView)
# admin.site.register(ListViewField)
# admin.site.register(ListViewFilter)
# admin.site.register(CallLog)3