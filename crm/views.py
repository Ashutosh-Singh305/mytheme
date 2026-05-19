import json
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponseForbidden, HttpResponseNotFound
from crm.admin import LeadAdmin
from django.contrib import messages
from django.contrib.auth.decorators import login_required,permission_required
from django.shortcuts import render, get_object_or_404, redirect
from crm.forms import *
from django.contrib.admin.views.decorators import staff_member_required
from django.apps import apps
from crm.choices import *
import pandas as pd
import os
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Q
# for dashboard
from crm.ip_utils import get_client_ip
from crm.models import *
from django.db.models import Count, Sum, Avg,Case, When, F
from django.contrib.auth.views import LoginView
from django.db.models.functions import TruncMonth
from django.utils.dateformat import DateFormat
from django.urls import reverse_lazy
from django.http import JsonResponse
from crm.utils import apply_audit_logic, get_allowed_user_queryset, get_lead_allowed_user_queryset, get_visible_queryset
from django.db import transaction
from django.views.decorators.http import require_POST
from django.template.loader import render_to_string
from django.http import JsonResponse
# Create your views here.
@login_required
def WelcomeView(request):
    return render(request,"welcome.html")

def custom_permission_denied_view(request, exception=None):
    message = str(exception) if exception else None
    return render(request, '403.html', {
        'error_message': message
    }, status=403)
 
 
@login_required
@permission_required('crm.view_iprange', raise_exception=True)
def ip_list(request):

    ip_ranges = IPRange.objects.all()

    # FILTER
    status = request.GET.get('status')
    if status == 'active':
        ip_ranges = ip_ranges.filter(is_active=True)
    elif status == 'inactive':
        ip_ranges = ip_ranges.filter(is_active=False)

    # SEARCH
    search = request.GET.get('search')

    if search:
        search_lower = search.lower()

        query = Q(start_ip__icontains=search) | Q(end_ip__icontains=search)

        if search_lower == 'active':
            query |= Q(is_active=True)

        elif search_lower == 'inactive':
            query |= Q(is_active=False)

        ip_ranges = ip_ranges.filter(query)
    # SORT
    sort = request.GET.get('sort', 'id')
    direction = request.GET.get('dir', 'desc')

    allowed = ['id', 'start_ip', 'end_ip', 'is_active']
    if sort not in allowed:
        sort = 'id'

    ordering = f"-{sort}" if direction == "desc" else sort
    ip_ranges = ip_ranges.order_by(ordering)

    # PAGINATION
    paginator = Paginator(ip_ranges, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj': page_obj,
        'current_sort': sort,
        'current_dir': direction,
        'current_status': status,
        "is_paginated" : page_obj.has_other_pages(),
    }

    # 🔥 KEY CHANGE
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        context['is_ajax'] = True
        return render(request, 'crm/ip/ip_list.html', context)

    return render(request, 'crm/ip/ip_list.html', context)

@login_required
@permission_required('crm.add_iprange', raise_exception=True)
def ip_create(request):

    if request.method == 'POST':
        form = IPRangeForm(request.POST)

        if form.is_valid():
            ip = form.save(commit=False)

            # 🔥 APPLY AUDIT LOGIC
            apply_audit_logic(ip, request, is_create=True)

            ip.save()

            messages.success(
                request,
                f"IP Range {ip.start_ip} - {ip.end_ip} created successfully!"
            )
            return redirect('ip-list')

        else:
            messages.error(request, "Please correct the errors below.")

    else:
        form = IPRangeForm()

    return render(request, 'crm/ip/ip_form.html', {'form': form})

@login_required
@permission_required('crm.change_iprange', raise_exception=True)
def ip_edit(request, pk):
    ip = get_object_or_404(IPRange, pk=pk)

    if request.method == 'POST':
        form = IPRangeForm(request.POST, instance=ip)

        if form.is_valid():
            ip = form.save(commit=False)

            # 🔥 APPLY AUDIT LOGIC (UPDATE MODE)
            apply_audit_logic(ip, request, is_create=False)

            ip.save()

            messages.success(
                request,
                f"IP Range {ip.start_ip} - {ip.end_ip} updated successfully!"
            )
            return redirect('ip-list')

        else:
            messages.error(request, "Please correct the errors below.")

    else:
        form = IPRangeForm(instance=ip)

    return render(request, 'crm/ip/ip_form.html', {
        'form': form,
        'is_edit': True,
        'object': ip
    })
@login_required
@permission_required('crm.view_iprange', raise_exception=True)
def ip_detail(request, pk):
    if not request.user.is_superuser:
        return render(request, "403.html")

    ip = get_object_or_404(IPRange, pk=pk)

    return render(request, 'crm/ip/ip_detail.html', {
        'ip': ip
    })
    
@login_required
@permission_required('crm.delete_iprange', raise_exception=True)
def ip_delete(request, pk):

    ip = get_object_or_404(IPRange, pk=pk)
    ip.delete()
    return redirect('ip-list')


#  CREATE
@login_required
@permission_required('auth.add_user', raise_exception=True)
def user_create(request):
    if not request.user.is_superuser:
        return render(request, "403.html")

    if request.method == 'POST':

        user_form = UserRegistrationForm(request.POST)
        profile_form = UserProfileForm(request.POST)

        if user_form.is_valid() and profile_form.is_valid():

            # SAVE USER
            user = user_form.save(commit=False)

            user.is_active = user_form.cleaned_data.get('is_active')
            user.is_staff = user_form.cleaned_data.get('is_staff')
            user.is_superuser = user_form.cleaned_data.get('is_superuser')
            
            # DATE JOINED DEFAULT
            if user_form.cleaned_data.get('date_joined'):
                user.date_joined = user_form.cleaned_data.get('date_joined')
            else:
                user.date_joined = timezone.now()

            user.save()

            # GROUP ASSIGN
            groups = user_form.cleaned_data.get('groups')
            if groups:
                user.groups.set(groups)

            # SAVE PROFILE
            profile = profile_form.save(commit=False)
            profile.user = user
            profile.created_by = request.user
            profile.assigned_to = request.user
            profile.save()

            messages.success(
                request,
                f"Employee {user.username} created successfully!"
            )

            return redirect('user-list')

        else:
            messages.error(request, 'Please correct the errors below.')

    else:
        user_form = UserRegistrationForm()
        profile_form = UserProfileForm()

    context = {
        'user_form': user_form,
        'profile_form': profile_form,
    }

    return render(
        request,
        'crm/user/user_registration.html',
        context
    )

@login_required
@permission_required('auth.view_user', raise_exception=True)
def user_list(request):

    if not request.user.is_superuser:
        return render(request, "403.html")

    # MAIN QUERY
    users = User.objects.select_related(
        'userprofile',
        'userprofile__role',
        'userprofile__manager',
        'userprofile__branch'
    ).all()

    # STATUS FILTER
    status = request.GET.get('status')

    if status == 'active':
        users = users.filter(is_active=True)

    elif status == 'inactive':
        users = users.filter(is_active=False)

    # ROLE FILTER
    role = request.GET.get('role')

    if role:
        users = users.filter(
            userprofile__role_id=role
        )

    # SEARCH
    search = request.GET.get('search')

    # BRANCH FILTER
    branch = request.GET.get('branch')

    if branch:
        users = users.filter(
            userprofile__branch_id=branch
        )

    if search:

        users = users.filter(

            Q(username__icontains=search) |
            Q(email__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |

            Q(userprofile__emp_code__icontains=search) |
            Q(userprofile__branch__name__icontains=search) |
            Q(userprofile__role__name__icontains=search) |
            Q(userprofile__role__code__icontains=search)

        )

    # SORT
    sort = request.GET.get('sort', 'date_joined')
    direction = request.GET.get('dir', 'desc')

    allowed = [
        'id',
        'username',
        'first_name',
        'is_active',

        'userprofile__branch__name',
        'userprofile__role__name',
    ]

    if sort not in allowed:
        sort = 'date_joined'

    ordering = f"-{sort}" if direction == "desc" else sort

    users = users.order_by(ordering)

    # PAGINATION
    paginator = Paginator(users, 10)

    page_obj = paginator.get_page(
        request.GET.get('page')
    )

    # AJAX
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':

        html = render_to_string(
            'crm/user/user_table_partial.html',
            {'page_obj': page_obj},
            request=request
        )

        return JsonResponse({
            'html': html
        })

    return render(request, 'crm/user/user_list.html', {

        'page_obj': page_obj,

        'current_sort': sort,
        'current_dir': direction,

        'current_status': status,
        'current_role': role,
        'current_branch': branch,
        'branches': Branch.objects.all(),
        'roles': Role.objects.filter(is_active=True),
    })
#  UPDATE
@login_required
@permission_required('auth.change_user', raise_exception=True)
def user_edit(request, pk):

    if not request.user.is_superuser:
        return render(request, "403.html")

    user = get_object_or_404(User, pk=pk)

    # GET OR CREATE PROFILE
    profile, created = UserProfile.objects.get_or_create(
        user=user
    )

    if request.method == 'POST':

        user_form = UpdateUserRegistration(
            request.POST,
            instance=user
        )

        profile_form = UserProfileForm(
            request.POST,
            instance=profile
        )

        if user_form.is_valid() and profile_form.is_valid():

            with transaction.atomic():

                # SAVE USER
                updated_user = user_form.save(commit=False)

                updated_user.is_active = user_form.cleaned_data.get('is_active')
                updated_user.is_staff = user_form.cleaned_data.get('is_staff')
                updated_user.is_superuser = user_form.cleaned_data.get('is_superuser')

                updated_user.save()

                # SAVE GROUPS
                groups = user_form.cleaned_data.get('groups')
                updated_user.groups.set(groups)

                # SAVE PROFILE
                updated_profile = profile_form.save(commit=False)
                updated_profile.user = updated_user
                updated_profile.modified_by = request.user
                updated_profile.save()

            messages.success(
                request,
                f"User {updated_user.username} updated successfully!"
            )

            return redirect('user-list')

        else:
            messages.error(
                request,
                "Please correct the errors below."
            )

    else:

        user_form = UpdateUserRegistration(
            instance=user
        )

        profile_form = UserProfileForm(
            instance=profile
        )

        # PRESELECT GROUPS
        user_form.fields['groups'].initial = user.groups.all()

    context = {
        'user_form': user_form,
        'profile_form': profile_form,
        'user': user
    }

    return render(
        request,
        "crm/user/user_edit.html",
        context
    )

#  READ (DETAIL)
@login_required
@permission_required('auth.view_user', raise_exception=True)
def user_detail(request, pk):

    if not request.user.is_superuser:
        return render(request, "403.html")

    user = get_object_or_404(User, pk=pk)

    # SAFE PROFILE FETCH
    profile = getattr(user, 'userprofile', None)

    context = {
        'user': user,
        'profile': profile,
        'user_groups': user.groups.all()
    }

    return render(
        request,
        'crm/user/user_detail.html',
        context
    )
    
#  DELETE
@login_required
@permission_required('auth.delete_user', raise_exception=True)
def user_delete(request, pk):
    if not request.user.is_superuser:
        return render(request,"403.html")
    user = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        username = user.username
        user.delete()
        messages.success(request, f"ðŸ—‘ï¸ User {username} deleted successfully.")
        return redirect('user-list')

    return render(request, 'crm/user/user_confirm_delete.html', {'user': user})

@login_required
def myProfile(request):
    my_profile = get_object_or_404(UserProfile, user=request.user)
    return render(request, 'crm/user/my_profile.html', {'my_profile': my_profile})

# Create your views here
class CustomLoginView(LoginView):
    template_name = "login.html"
    def dispatch(self, request, *args, **kwargs):
        # print("IP DEBUG:", get_client_ip(request))
        # print("RAW HEADER:", request.META.get("HTTP_X_FORWARDED_FOR"))
        # print("REMOTE_ADDR:", request.META.get("REMOTE_ADDR"))
        if request.user.is_authenticated:
            return redirect(reverse_lazy('my_profile'))
        return super().dispatch(request, *args, **kwargs)

    def form_invalid(self, form):
        """
        This runs when authentication fails.
        We detect if failure was due to IP restriction.
        """

        # 🔥 Check if backend flagged IP restriction
        if hasattr(self.request, "ip_blocked") and self.request.ip_blocked:
            return render(self.request, "no_access.html", {
                "ip": getattr(self.request, "blocked_ip", "Unknown")
            })

        # Normal invalid credentials case
        return super().form_invalid(form)

    def get_success_url(self):
        return self.get_redirect_url() or reverse_lazy('my_profile')


#Function to get accessible fields for the logged-in user
def get_accessible_fields(user, model_name):
    user_profile = UserProfile.objects.get(user=user)
    field_permissions = FieldAccessControl.objects.filter(role=user_profile.role, model_name=model_name)

    viewable_fields = {fp.field_name for fp in field_permissions if fp.can_view}
    editable_fields = {fp.field_name for fp in field_permissions if fp.can_edit}

    return viewable_fields, editable_fields
   
# Dashboard Views
@login_required
@permission_required('crm.can_access_crm_dashboard', raise_exception=True)
def dashboard(request):
    return render(request, 'crm/dashboard/dashboard.html')


@login_required
@permission_required('crm.can_access_crm_dashboard', raise_exception=True)
def leadDashboard(request):
    # - Channels (doughnut) -
    channel_data = list(
        Lead.objects.values('channel_name').annotate(total=Count('id'))
    )

    # - Monthly status (bar) -
    monthly_raw = Lead.objects.annotate(
        month=TruncMonth('created_date')
    ).values('month', 'status').annotate(count=Count('id')).order_by('month')

    monthly_status = [
        {
            'month': DateFormat(item['month']).format('Y-m-d'),
            'status': item['status'],
            'count': item['count']
        }
        for item in monthly_raw
    ]
    # - Totals (cards) -
    totals = Lead.objects.aggregate(
        total_net=Sum(Case(When(status="disbursed", then=F("net_disbursed")))),
        total_gross=Sum(Case(When(status="disbursed", then=F("gross_disbursed")))),
        total_approved=Sum(Case(When(status="approved", then=F("approved_amount")))),
        lead_count=Count('id')
    )

    return render(request, 'crm/dashboard/lead_dashboard.html', {
        'channels': channel_data,
        'monthly_status': monthly_status,
        'totals': totals
    })

# Tse Dashboard View 
@login_required
def tse_dashboard(request):
    if not request.user.has_perm("crm.can_access_crm_dashboard"):
        raise PermissionDenied("You do not have permission to access Dashboard.")
    user = request.user
    today = timezone.localdate()

    # BASE QUERYSET (NO FILTERS)
    base_qs = get_visible_queryset(Lead, user).select_related(
        'tele_sales_executive',
        'team_lead',
        'sm',
        'business_manager',
        'business_head',
        'bank',
        'lender_name'
    )

    # SEARCH / SORT INPUT
    search = request.GET.get("search", "").strip()
    sort = request.GET.get("sort", "").strip()
    status_filter = request.GET.get("status")
    lead_source_filter = request.GET.get("lead_source")

    # FILTERED QUERYSET (FOR UI)
    leads_qs = base_qs

    if search:
        leads_qs = leads_qs.filter(
            Q(name__icontains=search) |
            Q(mobile_number__icontains=search) |
            Q(company_name__icontains=search)
        )

    if lead_source_filter:
        leads_qs = leads_qs.filter(lead_source=lead_source_filter)

    if status_filter:
        leads_qs = leads_qs.filter(status=status_filter)
    else:
        leads_qs = leads_qs.filter(
            status__in=[
                'new', 'not_interested', 'waiting_for_docs', 'OTP','Future Lead',
                'Ringing', 'Switched_Off', 'call_back', 'follow_up','invalid_number','loan_needed'
            ]
        )

   
    if sort:
        leads_qs = leads_qs.order_by(sort)
    else:
        leads_qs = leads_qs.order_by('-modified_at')

    # KPI (ALWAYS FROM BASE_QS)
    interested_leads = base_qs.filter(status='interested').count()

    disbursed_amount = base_qs.filter(
        status='disbursed'
    ).aggregate(total=Sum('net_disbursed'))['total'] or 0

    hot_leads = base_qs.filter(
        Q(cibil_score__gte=740),
        Q(monthly_salary__gte=40000)
    ).count()

    applications = base_qs.filter(
        status__in=[
            'waiting_for_docs',
            'OTP',
            'Approved',
            'Scorecard Approved',
            'loan_needed',
        ]
    ).count()

    # FOLLOWUPS / CALLS (USER BASED)
    followup_qs = get_visible_queryset(LeadFollowUp, user)
    

    calls_today = base_qs.filter(
        modified_at__date=today  
    ).count()

    followups_today = followup_qs.filter(
        follow_up_date__date=today
    ).count()

    # PAGINATION
    paginator = Paginator(leads_qs, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)


    return render(request, 'crm/dashboard/tse_dashboard.html', {
        "leads": page_obj,
        "page_obj": page_obj,

        # KPI
        "calls_today": calls_today,
        "followups_today": followups_today,
        "hot_leads": hot_leads,
        "interested_leads": interested_leads,
        "applications": applications,
        "disbursed_amount": disbursed_amount,

        # Filters
        "selected_status": status_filter,
        "selected_lead_source": lead_source_filter,

        # Choices
        "LEAD_STATUS_CHOICES": LEAD_STATUS_CHOICES,
        "lead_type_choices": LEAD_TYPE_CHOICES,
        "employment_type_choices": EMPLOYMENT_TYPE_CHOICES,
        "lender_name_choices": Bank.objects.all(),
        "team_leaders": get_lead_allowed_user_queryset(request.user, "team_lead"),
        "tele_executive": get_lead_allowed_user_queryset(request.user, "tele_sales_executive")
        
    })

@login_required
def get_lead_detail(request, lead_id):
    lead = get_object_or_404(
            get_visible_queryset(Lead, request.user),
            id=lead_id
        )
    return JsonResponse({
        "id": lead.id,
        "name": lead.name,
        "mobile": lead.mobile_number,
        "status": lead.get_status_display(),
        "status_key": lead.status,

        #  PERSONAL
        "location": lead.location or "",
        "pan": lead.pan or "",
        "dob": str(lead.dob or ""),
        "description": lead.description or "",

        #  JOB
        "company": lead.company_name or "",
        "salary": str(lead.monthly_salary or ""),


        #  META
        "lead_source": lead.lead_source or "",
        "lender_id": getattr(lead.lender_name, "id", ""),
        "loan_required": lead.require_loan_amount or "",
        "existing_loan_details": lead.existing_loan_details or "",
        "employment_type": lead.employment_type or "",
        "existing_cc_details": lead.existing_cc_details or "",
        
       

        #  EXTRA
        "note": lead.description or "",
        "follow_up_date": timezone.localtime(lead.follow_up_date).strftime("%Y-%m-%dT%H:%M") if lead.follow_up_date else "",
        "LEAD_TYPE_CHOICES":LEAD_TYPE_CHOICES,
        "assigned_to": lead.assigned_to.username if lead.assigned_to else "",
        "last_updated": timezone.localtime(lead.modified_at).strftime("%d/%m/%Y %I:%M %p") if lead.modified_at else "",
    })

@login_required
def update_lead_full(request):
    if not request.user.has_perm("crm.change_lead"):
        return HttpResponseForbidden("<h3>You do not have permission to Edit Lead.</h3>")
    
    lead_id = request.POST.get("lead_id")

    if not lead_id or lead_id == "undefined":
        return JsonResponse({
            "status": "error",
            "message": "Invalid lead selected."
        }, status=400)

    lead = get_object_or_404(Lead, id=lead_id)
    
    if request.method == "POST":
        lead = get_object_or_404(
            Lead,
            id=request.POST.get("lead_id")
        ) 
        print("UPDATE LEAD - Fetched Lead:", lead)  # 👈 DEBUG
    
        # ACCESS CHECK (IMPORTANT)
        if lead not in get_visible_queryset(Lead, request.user):
            return JsonResponse({
                "status": "error",
                "message": "Access denied. Please refresh the page."
            }, status=403)
            
        name = request.POST.get("name")
        if name not in [None, ""]:
            lead.name = name
            
        location = request.POST.get("location")
        company_name = request.POST.get("company")
        salary = request.POST.get("salary") or None
        status = request.POST.get("status")
        note = request.POST.get("note")
        follow_up_date = request.POST.get("follow_date")
        employement_type = request.POST.get("employment_type")
        existing_cc_details = request.POST.get("existing_cc_details")
        
        if employement_type not in [None, ""]:
            lead.employment_type = employement_type
        
        if existing_cc_details not in [None, ""]:
            lead.existing_cc_details = existing_cc_details
        

        if note not in [None, ""]:
            lead.description = note

        if follow_up_date not in [None, ""]:
            lead.follow_up_date = follow_up_date
        
        if location not in [None, ""]:
            lead.location = location
   
        if company_name not in [None, ""]:
            lead.company_name = company_name
       
        if salary not in [None, ""]:
            lead.monthly_salary = salary
            
        if status not in [None, ""]: 
            lead.status = status

            
        lead.modified_by = request.user
        lead.save()

       
        if follow_up_date not in [None, ""]:
            LeadFollowUp.objects.create(
                lead=lead,
                user=request.user,
                note=note,
                status=lead.status,
                follow_up_date=follow_up_date,
                assigned_to=request.user,
                created_by=request.user,
            )

        return JsonResponse({"status": "success",
                             "name": lead.name,
                            "status_key": lead.status,
                            "status_label": lead.get_status_display(),
                            "follow_up_date": lead.follow_up_date,
                             })
from django.utils.dateparse import parse_datetime
@login_required
def create_lead_api(request):
    if not request.user.has_perm("crm.add_lead"):
        return HttpResponseForbidden("<h3>You do not have permission to Add Lead.</h3>")
    
    if request.method == "POST":
        try:
            # - Extract & parse date safely -
            follow_up_date_raw = request.POST.get('follow_up_date') or None
            follow_up_date = None

            follow_up_date_raw = request.POST.get('follow_up_date')
            follow_up_date = None

            if follow_up_date_raw:
                follow_up_date = parse_datetime(follow_up_date_raw)

                if not follow_up_date:
                    return JsonResponse({
                        "status": "error",
                        "message": "Invalid date format"
                    }, status=400)

                if timezone.is_naive(follow_up_date):
                    follow_up_date = timezone.make_aware(follow_up_date)

            # - Create Lead -
            lead = Lead.objects.create(
                name=request.POST.get('name'),
                location=request.POST.get('location'),
                company_name=request.POST.get('company_name'),
                monthly_salary=request.POST.get('monthly_salary') or None,
                status=request.POST.get('status'),
                lead_source=request.POST.get('lead_source'),
                follow_up_date=follow_up_date,
                mobile_number=request.POST.get('mobile_number'),
                team_lead=User.objects.get(id=request.POST.get('team_lead')) if request.POST.get('team_lead') else None,
                tele_sales_executive=User.objects.get(id=request.POST.get('tse')) if request.POST.get('tse') else None,
                description=request.POST.get('description'),
                created_by=request.user,
                assigned_to=request.user
            )

            # - Create FollowUp (WITH PERMISSION CHECK) -
            if follow_up_date:
                LeadFollowUp.objects.create(
                    lead=lead,
                    user=request.user,
                    note=request.POST.get('description'),
                    follow_up_date=follow_up_date,
                    status=lead.status,
                    created_by = request.user,
                    assigned_to = request.user
                )

            return JsonResponse({
                "status": "success",
                "lead_id": lead.id
            })

        except Exception as e:
            print("CREATE LEAD ERROR:", str(e))  # 👈 IMPORTANT
            return JsonResponse({
                "status": "error",
                "message": str(e)
            }, status=400)


@login_required
@permission_required('crm.can_access_hr_module', raise_exception=True)
def hr_dashboard(request):
    user = request.user
    today = timezone.localdate()

    
    base_qs = get_visible_queryset(CandidateOnboarding, user).select_related(
        'recruiter',
        'interviewer',
        'reporting_manager'
    )

    
    search = request.GET.get("search", "").strip()
    sort = request.GET.get("sort", "").strip()
    status_filter = request.GET.get("status")
    applied_for_filter = request.GET.get("applied_for")

   
    candidates_qs = base_qs

    if search:
        candidates_qs = candidates_qs.filter(
            Q(full_name__icontains=search) |
            Q(phone__icontains=search) |
            Q(employee_code__icontains=search)
        )
    if applied_for_filter:
        candidates_qs = candidates_qs.filter(applied_for=applied_for_filter)

    

    if status_filter:
        candidates_qs = candidates_qs.filter(candidate_status=status_filter)

    
    if sort:
        candidates_qs = candidates_qs.order_by(sort)
    else:
        candidates_qs = candidates_qs.order_by('-modified_at')

    # KPI (HR SPECIFIC)
    new_candidates = base_qs.filter(candidate_status='New').count()

    contacted_today = base_qs.filter(
        calling_date=today
    ).count()

    interviews_today = base_qs.filter(
        interview_date=today
    ).count()

    shortlisted = base_qs.filter(
        candidate_status='Shortlisted'
    ).count()

    joining_soon = base_qs.filter(
        expected_joining_date__gte=today
    ).count()
    
    training_pending = base_qs.filter(
        training_status='Not Started'
    ).count()

    
    paginator = Paginator(candidates_qs, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

   
    return render(request, 'crm/dashboard/hr_dashboard.html', {
        "candidates": page_obj,
        "page_obj": page_obj,

        # KPI
        "new_candidates": new_candidates,
        "contacted_today": contacted_today,
        "interviews_today": interviews_today,
        "shortlisted": shortlisted,
        "joining_soon": joining_soon,
        "training_pending": training_pending,

        # Filters
        "selected_status": status_filter,
        "selected_applied_for": applied_for_filter,
        

        # Choices
        "CANDIDATE_STATUS_CHOICES": CANDIDATE_STATUS_CHOICES,
        "CANDIDATE_SOURCE_CHOICE": CANDIDATE_SOURCE_CHOICE,
        "position_applied_for_choices": CandidateOnboarding._meta.get_field('applied_for').choices,
        "source_choices": CandidateOnboarding._meta.get_field('source').choices,
        "employment_status_choices": CandidateOnboarding._meta.get_field('employment_status').choices,
        "candidate_status_choices": CandidateOnboarding._meta.get_field('candidate_status').choices,
        "recruiters":get_allowed_user_queryset(request.user)
    })
    
@login_required
def get_candidate_detail(request, candidate_id):
    candidate = get_object_or_404(
        get_visible_queryset(CandidateOnboarding, request.user), id=candidate_id)

    return JsonResponse({
        "id": candidate.id,
        "name": candidate.full_name,
        "position_applied_for": candidate.applied_for or "",
        "experince": str(candidate.experience or ""),
        "employement_status": candidate.get_employment_status_display(),
        "candidate_status": candidate.get_candidate_status_display(),
        "candidate_area": candidate.candidate_area or "",
        # "dob": str(candidate.date_of_birth or ""),
        "calling_date": str(candidate.calling_date or ""),
        "source": candidate.get_source_display(),
        "mobile": candidate.phone,
        # "calling_date": candidate.calling_date.strftime("%Y-%m-%d") if candidate.calling_date else "",
        "interview_date": candidate.interview_date.strftime("%Y-%m-%d") if candidate.interview_date else "",
        "date_of_joining": candidate.actual_joining_date.strftime("%Y-%m-%d") if candidate.actual_joining_date else "",
        "status_key": candidate.candidate_status,
    

        #  EXTRA
        "note": candidate.recruiter_feedback or "",
        "assigned_to": candidate.assigned_to.username if candidate.assigned_to else "",
        "modified_date": timezone.localtime(candidate.modified_at).strftime("%d/%m/%Y %I:%M %p") if candidate.modified_at else "",
        "modified_by": candidate.modified_by.username if candidate.modified_by else "",
        "recruiter_id": candidate.recruiter.id if candidate.recruiter else "",
        "recruiter_name": (
            candidate.recruiter.get_full_name() 
            if candidate.recruiter and candidate.recruiter.get_full_name()
            else candidate.recruiter.username if candidate.recruiter else ""
        ),
    })
    
@login_required
def update_candidate(request):
    if request.method == "POST":

        candidate = get_object_or_404(
            CandidateOnboarding,
            id=request.POST.get("candidate_id")
        )

        # Permission check
        if candidate not in get_visible_queryset(CandidateOnboarding, request.user):
            return JsonResponse({
                "status": "error",
                "message": "Access denied. Please refresh the page."
            }, status=403)

        
        # Helper functions
        def update_if_present(field, attr):
            value = request.POST.get(field)
            if value not in [None, ""]:
                setattr(candidate, attr, value)

        def parse_date(field):
            val = request.POST.get(field)
            if val:
                try:
                    return datetime.strptime(val, "%Y-%m-%d").date()
                except ValueError:
                    return None
            return None

        
        # Text fields
        update_if_present("full_name", "full_name")
        update_if_present("applied_for", "applied_for")
        update_if_present("experience", "experience")
        update_if_present("employment_status", "employment_status")
        update_if_present("candidate_status", "candidate_status")
        update_if_present("candidate_area", "candidate_area")
        update_if_present("source", "source")

        
        # Date fields
        calling_date = parse_date("calling_date")
        if calling_date:
            candidate.calling_date = calling_date

        interview_date = parse_date("interview_date")
        if interview_date:
            candidate.interview_date = interview_date

        doj = parse_date("doj")
        if doj:
            candidate.actual_joining_date = doj

        
        # Recruiter (ForeignKey)
        recruiter_id = request.POST.get("recruiter")

        if recruiter_id not in [None, ""]:
            allowed_users = get_allowed_user_queryset(request.user)

            recruiter = allowed_users.filter(id=recruiter_id).first()

            if not recruiter:
                return JsonResponse({
                    "status": "error",
                    "message": "Invalid recruiter selection"
                }, status=403)

            candidate.recruiter = recruiter

        
        # Note / Feedback
        note = request.POST.get("note")
        if note not in [None, ""]:
            candidate.recruiter_feedback = note

        
        # Audit fields
        candidate.modified_by = request.user
        candidate.save()

        return JsonResponse({
            "status": "success",
            "message": "Candidate updated successfully",
            "candidate_id": candidate.id,
            "full_name": candidate.full_name,
            "candidate_status": candidate.candidate_status,
            "candidate_status_label": candidate.get_candidate_status_display(),
            "recruiter": candidate.recruiter.id if candidate.recruiter else None,
            "recruiter_name": candidate.recruiter.username if candidate.recruiter else None,
        })

    return JsonResponse({
        "status": "error",
        "message": "Invalid request method"
    }, status=405)
    
        
from datetime import datetime
@require_POST
@login_required
def create_candidate(request):

    def get_value(field):
        val = request.POST.get(field)
        return val.strip() if val else None

    def parse_date(field):
        val = request.POST.get(field)
        if val:
            try:
                return datetime.strptime(val, "%Y-%m-%d").date()
            except ValueError:
                return None
        return None

    # REQUIRED FIELDS
    full_name = get_value("full_name")
    applied_for = get_value("applied_for")
    phone = get_value("phone")
    recruiter_id = request.POST.get("recruiter")

    if not full_name:
        return JsonResponse({"status": "error", "message": "Full name is required"}, status=400)

    if not phone:
        return JsonResponse({"status": "error", "message": "Mobile number is required"}, status=400)

    if not phone.isdigit() or len(phone) != 10:
        return JsonResponse({"status": "error", "message": "Mobile number must be 10 digits"}, status=400)

    # VALIDATE RECRUITER
    recruiter = None
    if not recruiter_id:
        return JsonResponse({
            "status": "error",
            "message": "Recruiter is required"
        }, status=400)

    # VALIDATE RECRUITER
    allowed_users = get_allowed_user_queryset(request.user)

    recruiter = allowed_users.filter(id=recruiter_id).first()

    if not recruiter:
        return JsonResponse({
            "status": "error",
            "message": "Invalid recruiter selection"
        }, status=403)

    # CREATE OBJECT
    candidate = CandidateOnboarding.objects.create(
        full_name=full_name,
        phone=phone,
        applied_for=applied_for,

        experience=get_value("experience"),
        employment_status=get_value("employment_status"),
        candidate_status=get_value("candidate_status") or "New",
        candidate_area=get_value("candidate_area"),
        source=get_value("source"),

        calling_date=parse_date("calling_date"),
        # date_of_birth=parse_date("dob"),
        interview_date=parse_date("interview_date"),
        actual_joining_date=parse_date("doj"),

        recruiter=recruiter,   # ✅ SAFE FK

        recruiter_feedback=get_value("note"),

        created_by=request.user,
        assigned_to=request.user,
        modified_by=request.user,
    )

    return JsonResponse({
        "status": "success",
        "message": "Candidate created successfully",
        "candidate_id": candidate.id,
        "full_name": candidate.full_name,
        "candidate_status": candidate.candidate_status,
        "candidate_status_label": candidate.get_candidate_status_display(),
    }, status=201)

import requests

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt


def get_smartflo_token():

    response = requests.post(
        "https://api-smartflo.tatateleservices.com/v1/auth/login",

        json={
            "email": "DEMO.2611",
            "password": "Admin@231"
        },

        headers={
            "content-type": "application/json"
        },

        timeout=30
    )

    data = response.json()

    if not response.ok:
        raise Exception(data)

    token = data.get("access_token")

    if not token:
        raise Exception("Access token missing")

    return token

@login_required
@csrf_exempt
def test_smartflo(request):

    if request.method != "POST":

        return JsonResponse({
            "status": "error",
            "message": "Invalid request"
        })

    mobile = request.POST.get("mobile")

    if not mobile:

        return JsonResponse({
            "status": "error",
            "message": "Mobile number missing"
        })

    mobile = str(mobile).replace("+", "").strip()

    if not mobile.startswith("91"):
        mobile = "91" + mobile

    try:

        token = get_smartflo_token()

        payload = {
            "async": 1,
            "agent_number": "0607621620001",
            "destination_number": mobile,
            "caller_id": "918069879661"
        }

        response = requests.post(
            "https://api-smartflo.tatateleservices.com/v1/click_to_call",
            json=payload,
            headers={
                "accept": "application/json",
                "Authorization": token,
                "content-type": "application/json"
            },
            timeout=30
        )

        data = response.json()

        if not response.ok:

            return JsonResponse({
                "status": "error",
                "message": data
            })

        return JsonResponse({
            "status": "success",
            "data": data
        })

    except Exception as e:

        return JsonResponse({
            "status": "error",
            "message": str(e)
        })




# @login_required
# @csrf_exempt
# def test_smartflo(request):

#     mobile = request.POST.get("mobile")

#     if not mobile:
#         return JsonResponse({
#             "status": "error",
#             "message": "Mobile number missing"
#         })

#     url = "https://api-smartflo.tatateleservices.com/v1/click_to_call"

#     payload = {
#         "async": 1,
#         "agent_number": "0607621620002",
#         "destination_number": mobile,
#         "caller_id": "918069879661"
#     }

#     headers = {
#         "accept": "application/json",

#         # REMOVE EXTRA SPACE BEFORE TOKEN
#         "Authorization": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJodHRwczovL2Nsb3VkcGhvbmUudGF0YXRlbGVzZXJ2aWNlcy5jb20vYXBpL3YxL2F1dGgvbG9naW4iLCJpYXQiOjE3NzgwNjUxMzksImV4cCI6MTc3ODA2ODczOSwibmJmIjoxNzc4MDY1MTM5LCJqdGkiOiJNT2tBTWZydDFVaWdmT2RIIiwic3ViIjoiNzYyMTYyIiwiY2xpZW50X2lkIjo3NjIxNjIsImNyIjpmYWxzZX0.UkZWEDAi7SSBuNy263dlyxUJfsfNFIMbKWRw5YRd7O0",

#         "content-type": "application/json"
#     }

#     try:

#         response = requests.post(
#             url,
#             json=payload,
#             headers=headers,
#             timeout=30
#         )

#         return JsonResponse({
#             "status": "success",
#             "data": response.json()
#         })

#     except Exception as e:

#         return JsonResponse({
#             "status": "error",
#             "message": str(e)
#         })

######## Lead Bulk Assignment ##########
@login_required
@permission_required('crm.can_access_bulk_assign', raise_exception=True)
def bulk_assign_leads(request):
    leads = get_visible_queryset(Lead, request.user)
    
    role_map = {
        # 'sm': ['SM','Business Manager','BH'],
        'team_lead': ['TL','Business Manager','SM','BH'],
        'business_manager': ['Business Manager','BH'],
        'business_head': ['BH'],
        'tele_sales_executive': ['TSE'],
    }

    lead_source_filter = request.GET.get("lead_source", "").strip()
    assigned_to = request.GET.get("assigned_to", "").strip()
    status = request.GET.get("status", "").strip()

    sort = request.GET.get("sort", "created_date")
    dir = request.GET.get("dir", "desc")
    

    #  SORTING
    sort_field = sort

    if sort == "assigned_to":
        sort_field = "assigned_to__username"
    
    if sort == "tele_sales_executive":
        sort_field = "tele_sales_executive__username"
        
    if sort == "team_lead":
        sort_field = "team_lead__username"

    if sort == "business_head":
        sort_field = "business_head__username"

    if sort == "business_manager":
        sort_field = "business_manager__username"

    if dir == "desc":
        sort_field = "-" + sort_field

    leads = leads.order_by(sort_field)
    
    # FILTERS (SAFE)
    if lead_source_filter and lead_source_filter != "None":
        leads = leads.filter(lead_source=lead_source_filter)

    if status and status != "None":
        leads = leads.filter(status=status)

    if assigned_to and assigned_to != "None":
        try:
            assigned_to_int = int(assigned_to)
            leads = leads.filter(assigned_to_id=assigned_to_int)
        except ValueError:
            pass  # ignore invalid input

    #  PAGINATION
    try:
        per_page = int(request.GET.get("per_page", 50))
    except ValueError:
        per_page = 50

    paginator = Paginator(leads, per_page)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # USERS LIST
    login_user = request.user
    profile = getattr(login_user, "userprofile", None)

    if login_user.is_superuser or (profile and profile.role.code == "ADMIN"):
        users = User.objects.filter(is_active=True)\
            .select_related('userprofile').order_by('username')

    elif not profile or not profile.branch:
        users = User.objects.filter(
            id=login_user.id,
            is_active=True
        ).select_related('userprofile')

    else:
        users = User.objects.filter(
            userprofile__branch=profile.branch,
            is_active=True
        ).select_related('userprofile').order_by('username')
    
    team_leads = users.filter(userprofile__role__in=role_map['team_lead'])
    business_heads = users.filter(userprofile__role__in=role_map['business_head'])
    business_managers = users.filter(userprofile__role__in=role_map['business_manager'])
    tse_users = users.filter(userprofile__role__in=role_map['tele_sales_executive'])

    return render(request, "crm/leads/bulk_assign.html", {
        "page_obj": page_obj,
        "users": users,
        "status_choices": Lead._meta.get_field('status').choices,
        "lead_source_choices": Lead._meta.get_field('lead_source').choices,
        "per_page": per_page,

        "selected_status": status,
        "selected_lead_source": lead_source_filter,
        "selected_assigned_to": assigned_to,
        
        "team_leads": team_leads,
        "business_heads": business_heads,
        "business_managers": business_managers,
        "tse_users": tse_users,

        "sort": sort,
        "dir": dir,
        
    })

@login_required
@require_POST
def assign_leads(request):

    lead_ids = request.POST.getlist("lead_ids[]")
    assigned_to = request.POST.get("assigned_to")
    tele_sales_executive = request.POST.get("tele_sales_executive")
    team_lead = request.POST.get("team_lead")
    business_head = request.POST.get("business_head")
    business_manager = request.POST.get("business_manager")

    if not lead_ids:
        return JsonResponse({"error": "No leads selected"}, status=400)

    #  SECURITY
    leads = get_visible_queryset(Lead, request.user).filter(id__in=lead_ids)

    update_data = {}

    #  ASSIGNED TO (WITH OLD LOGIC)
    if assigned_to:
        user = get_object_or_404(
            User.objects.select_related("userprofile"),
            id=assigned_to
        )

        update_data["assigned_to"] = user

        # PRESERVE OLD BEHAVIOR
        user_profile = getattr(user, "userprofile", None)
        if user_profile and user_profile.role == "TSE":
            update_data["tele_sales_executive"] = user

    # TELE SALES EXECUTIVE (MANUAL OVERRIDE)
    if tele_sales_executive:
        tse = get_object_or_404(
            User.objects.select_related("userprofile"),
            id=tele_sales_executive
        )
        update_data["tele_sales_executive"] = tse

    # TEAM LEAD
    if team_lead:
        tl = get_object_or_404(
            User.objects.select_related("userprofile"),
            id=team_lead
        )
        update_data["team_lead"] = tl

    # BUSINESS HEAD
    if business_head:
        bh = get_object_or_404(
            User.objects.select_related("userprofile"),
            id=business_head
        )
        update_data["business_head"] = bh

    # BUSINESS MANAGER
    if business_manager:
        bm = get_object_or_404(
            User.objects.select_related("userprofile"),
            id=business_manager
        )
        update_data["business_manager"] = bm

    # NOTHING TO UPDATE
    if not update_data:
        return JsonResponse({"error": "No fields to update"}, status=400)

    # BULK UPDATE
    with transaction.atomic():
        updated_count = leads.update(**update_data)

    return JsonResponse({
        "success": True,
        "updated": updated_count
    })

# Detail View
@login_required
def lead_detail(request, pk):
    # 1. Get the lead safely
    lead = get_visible_queryset(Lead, request.user).filter(pk=pk).first()
    if not lead:
        return HttpResponseNotFound("Lead not found or access denied.")

    # 2. Get field-level permissions
    viewable_fields, _ = get_accessible_fields(request.user, "Lead")

    # 3. Get admin fieldsets safely
    raw_fieldsets = getattr(LeadAdmin, "fieldsets", None) or []

    admin_fieldsets = []
    counter = 1

    for title, opts in raw_fieldsets:
        fields = opts.get("fields", [])

        # Filter fields based on user permissions
        filtered_fields = [f for f in fields if f in viewable_fields]

        # Skip empty sections (no visible fields)
        if not filtered_fields:
            continue

        admin_fieldsets.append({
            "id": f"section_{counter}",
            "title": title,
            "fields": filtered_fields,
        })
        counter += 1

    # 4. Build context
    context = {
        "lead": lead,
        "admin_fieldsets": admin_fieldsets,
        "viewable_fields": viewable_fields,
    }

    return render(request, "crm/leads/lead_detail.html", context)



@staff_member_required
def field_access_control_view(request):

    models = apps.get_models()

    model_choices = [
        (m.__name__, f"{m._meta.app_label}.{m.__name__}")
        for m in models
        if m._meta.app_label == 'crm'
    ]

    selected_model = request.GET.get('model') or request.POST.get('model')

    selected_role = request.GET.get('role') or request.POST.get('role')

    model_fields = []

    existing_access = {}

    # FK roles
    roles = Role.objects.filter(is_active=True).order_by("name")

    if selected_model:

        from django.contrib import admin

        model = apps.get_model('crm', selected_model)

        admin_class = admin.site._registry.get(model)

        if admin_class:

            fieldsets = admin_class.get_fieldsets(request)

            for _, options in fieldsets:

                fields = options.get('fields', [])

                for field in fields:

                    # grouped fields
                    if isinstance(field, (list, tuple)):
                        model_fields.extend(field)

                    else:
                        model_fields.append(field)

            # remove duplicates
            model_fields = list(dict.fromkeys(model_fields))

        else:

            # fallback
            model_fields = [
                f.name for f in model._meta.fields
            ]

        # EXISTING ACCESS
        if selected_role:

            access_controls = FieldAccessControl.objects.filter(
                model_name=selected_model,
                role_id=selected_role
            )

            existing_access = {
                control.field_name: (
                    control.can_view,
                    control.can_edit
                )
                for control in access_controls
            }

    # SAVE
    if request.method == 'POST':

        role_obj = Role.objects.filter(
            id=selected_role
        ).first()

        if not role_obj:

            messages.error(request, "Invalid role selected.")

            return redirect(request.path)

        for field in model_fields:

            can_view = request.POST.get(
                f'view__{field}'
            ) == 'on'

            can_edit = request.POST.get(
                f'edit__{field}'
            ) == 'on'

            FieldAccessControl.objects.update_or_create(

                model_name=selected_model,

                role=role_obj,

                field_name=field,

                defaults={
                    'can_view': can_view,
                    'can_edit': can_edit
                }
            )

        messages.success(
            request,
            f"Access controls updated for {selected_model} ({role_obj.name})"
        )

        return redirect(
            f"{request.path}?model={selected_model}&role={selected_role}"
        )

    return render(
        request,
        'admin/field_access_control.html',
        {
            'model_choices': model_choices,
            'model_fields': model_fields,

            'selected_model': selected_model,
            'selected_role': selected_role,

            'roles': roles,

            'existing_access': existing_access,
        }
    )
############### Report ################33
def run_report(report):
    model = apps.get_model(*report.model_name.split("."))
    qs = model.objects.all()

    group_by = report.group_by or 'id'
    agg_field = report.field or 'id'

    agg_func = {
        'count': Count,
        'sum': Sum,
        'avg': Avg
    }[report.aggregate]

    data = list(
        qs.values(group_by).annotate(result=agg_func(agg_field)).order_by(group_by)
    )
    return data

# def report_view(request, pk):
#     report = get_object_or_404(Report, pk=pk)
#     data = run_report(report)
#     labels = [str(item[report.group_by]) for item in data]
#     values = [item['result'] for item in data]
#     return render(request, 'admin/crm/report/report_view.html', {
#         'report': report,
#         'labels': labels,
#         'values': values
#     })

User = get_user_model()

def upload_leads_view(request):
    if request.method == 'POST':
        form = LeadCSVUploadForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = request.FILES['file']
            ext = os.path.splitext(uploaded_file.name)[1].lower()

            try:
                if ext == '.csv':
                    df = pd.read_csv(uploaded_file)
                elif ext == '.xlsx':
                    df = pd.read_excel(uploaded_file)
                else:
                    messages.error(request, "Unsupported file format. Please upload .csv or .xlsx.")
                    return redirect(request.path)

                created_count = 0

                for _, row in df.iterrows():
                    data = row.dropna().to_dict()

                    # Map Foreign Keys
                    # assigned_to_username â†’ assigned_to
                    user_fk_fields = {
                        'assigned_to_username': 'assigned_to',
                        'team_lead_username': 'team_lead',
                        'sm_username': 'sm',
                        'tele_sales_executive_username': 'tele_sales_executive',
                        'business_head_username': 'business_head',
                        'business_manager_username': 'business_manager',
                        'backend_executive_username': 'backend_executive_user',
                    }

                    for input_field, model_field in user_fk_fields.items():
                        if input_field in data:
                            try:
                                data[model_field] = User.objects.get(username=str(data[input_field]).strip())
                            except User.DoesNotExist:
                                messages.warning(request, f"User '{data[input_field]}' not found.")
                                data[model_field] = None
                            del data[input_field]

                    # bank_name â†’ bank
                    if 'bank_name' in data:
                        try:
                            data['bank'] = Bank.objects.get(name__iexact=str(data['bank_name']).strip())
                        except Bank.DoesNotExist:
                            messages.warning(request, f"Bank '{data['bank_name']}' not found.")
                            data['bank'] = None
                        del data['bank_name']

                    try:
                        Lead.objects.create(**data)
                        created_count += 1
                    except Exception as e:
                        messages.warning(request, f"Row skipped due to error: {e}")

                messages.success(request, f"{created_count} leads uploaded successfully.")
                return redirect('admin:crm_lead_changelist')

            except Exception as e:
                messages.error(request, f"Import failed: {str(e)}")
    else:
        form = LeadCSVUploadForm()

    return render(request, 'admin/crm/lead/upload_csv.html', {
        'form': form,
        'title': 'Upload Leads from File'
    })
    

# Lead Follow-up View
@login_required
@permission_required('crm.view_leadfollowup', raise_exception=True)
def leadfollowup_list(request):
    lead_id = request.GET.get("lead")
    if not lead_id:
        raise Http404("Lead context is required")

    lead = get_object_or_404(
        get_visible_queryset(Lead, request.user),
        pk=lead_id
    )

    queryset = get_visible_queryset(LeadFollowUp, request.user).filter(
        lead=lead
    ).order_by('-follow_up_date')

    paginator = Paginator(queryset, 50)
    page = request.GET.get('page')
    followups = paginator.get_page(page)

    return render(
        request,
        'crm/leadfollowup/leadfollowup_list.html',
        {
            'followups': followups,
            'lead': lead,                   
            'users': User.objects.all(),
            'LEAD_STATUS_CHOICES': LEAD_STATUS_CHOICES,
        }
    )

@login_required
@permission_required('crm.view_leadfollowup', raise_exception=True)
def leadfollowup_detail(request, pk):
    followup = get_object_or_404(LeadFollowUp, pk=pk)
    return render(request, 'crm/leadfollowup/leadfollowup_detail.html', {'followup': followup})

#CREATE
@login_required
@permission_required("crm.add_leadfollowup", raise_exception=True)
def leadfollowup_create(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)

    errors = {}

    lead_id = request.POST.get("lead")
    user_id = request.POST.get("user")
    note = request.POST.get("note", "").strip()
    follow_up_date = request.POST.get("follow_up_date")
    status = request.POST.get("status")

    #  VALIDATION 
    if not lead_id:
        errors["lead"] = ["Lead is required."]

    if not note:
        errors["note"] = ["Note is required."]

    if errors:
        return JsonResponse({"errors": errors}, status=400)

    lead = get_object_or_404(Lead, pk=lead_id)

    #  PARSE DATETIME 
    if follow_up_date:
        follow_up_date = timezone.make_aware(
            timezone.datetime.fromisoformat(follow_up_date)
        )
    else:
        follow_up_date = timezone.now()

    #  ATOMIC SAVE 
    with transaction.atomic():

        #Create Follow-Up
        followup = LeadFollowUp.objects.create(
            lead=lead,
            user_id=user_id or request.user.id,
            note=note,
            follow_up_date=follow_up_date,
            status=status,
            created_by=request.user,
        )

        #Update Lead current state
        lead.status = status or lead.status
        lead.description = note
        lead.modified_by = request.user
        lead.save(update_fields=["status", "description", "modified_by"])

    return JsonResponse({
        "success": True,
        "id": followup.id,
        "lead_status": lead.status,
        "date": followup.follow_up_date.strftime("%d %b %Y %H:%M"),
    })



@login_required
@permission_required("crm.change_leadfollowup", raise_exception=True)
def leadfollowup_update(request, pk):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)

    followup = get_object_or_404(LeadFollowUp, pk=pk)
    lead = followup.lead

    errors = {}

    user_id = request.POST.get("user")
    note = request.POST.get("note", "").strip()
    follow_up_date = request.POST.get("follow_up_date")
    status = request.POST.get("status")

    #  VALIDATION 
    if not note:
        errors["note"] = ["Note is required."]

    if errors:
        return JsonResponse({"errors": errors}, status=400)

    #  PARSE DATETIME 
    if follow_up_date:
        follow_up_date = timezone.make_aware(
            timezone.datetime.fromisoformat(follow_up_date)
        )
    else:
        follow_up_date = followup.follow_up_date  # keep existing

    #  ATOMIC UPDATE 
    with transaction.atomic():

        # Update FollowUp
        followup.user_id = user_id or followup.user_id
        followup.note = note
        followup.status = status
        followup.follow_up_date = follow_up_date
        followup.modified_by = request.user
        followup.save()

        # Sync Lead (same rule as CREATE)
        if lead:
            lead.status = status or lead.status
            lead.description = note
            lead.modified_by = request.user
            lead.save(update_fields=["status", "description", "modified_by"])

    return JsonResponse({
        "success": True,
        "id": followup.id,
        "lead_status": lead.status if lead else None,
        "date": followup.follow_up_date.strftime("%d %b %Y %H:%M"),
    })

@login_required
@permission_required('crm.delete_leadfollowup', raise_exception=True)
def leadfollowup_delete(request, pk):
    followup = get_object_or_404(LeadFollowUp, pk=pk)
    if request.method == 'POST':
        followup.delete()
        return redirect(f'/crm/leadfollowups/?lead={followup.lead_id}')
    return render(request, 'crm/leadfollowup/leadfollowup_confirm_delete.html', {'followup': followup})

# Document View
@login_required
@permission_required('crm.view_document', raise_exception=True)
def document_list(request):
    lead_id = request.GET.get("lead")
    if not lead_id:
        raise Http404("Lead context is required")

    lead = get_object_or_404(
        get_visible_queryset(Lead, request.user),
        pk=lead_id
    )

    queryset = get_visible_queryset(Document, request.user).filter(
        lead=lead
    ).order_by('-uploaded_at')

    paginator = Paginator(queryset, 50)
    page = request.GET.get('page')
    documents = paginator.get_page(page)

    return render(
        request,
        'crm/document.html',
        {
            'documents': documents,
            'lead': lead,                   
        }
    )

@login_required
@permission_required("crm.add_document", raise_exception=True)
def document_create(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)

    errors = {}

    lead_id = request.POST.get("lead")
    document_type = request.POST.get("document_type", "").strip()
    file = request.FILES.get("file")

    #  VALIDATION 
    if not lead_id:
        errors["lead"] = ["Lead is required."]

    if not document_type:
        errors["document_type"] = ["Document type is required."]

    if not file:
        errors["file"] = ["File is required."]

    if errors:
        return JsonResponse({"errors": errors}, status=400)

    lead = get_object_or_404(Lead, pk=lead_id)

    #  ATOMIC SAVE 
    with transaction.atomic():
        document = Document.objects.create(
            lead=lead,
            document_type=document_type,
            file=file,
            created_by=request.user,   # comes from AuditModel
        )

    return JsonResponse({
        "success": True,
        "id": document.id,
        "document_type": document.document_type,
        "filename": document.file.name.split("/")[-1],
        "uploaded_at": document.uploaded_at.strftime("%d %b %Y %H:%M"),
    })

@login_required
@permission_required("crm.change_document", raise_exception=True)
def document_update(request, pk):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)

    document = get_object_or_404(Document, pk=pk)

    errors = {}

    document_type = request.POST.get("document_type", "").strip()
    file = request.FILES.get("file")  # optional on update

    #  VALIDATION 
    if not document_type:
        errors["document_type"] = ["Document type is required."]

    if errors:
        return JsonResponse({"errors": errors}, status=400)

    #  ATOMIC UPDATE 
    with transaction.atomic():
        document.document_type = document_type

        # Replace file ONLY if a new one is uploaded
        if file:
            document.file = file

        document.modified_by = request.user  # AuditModel
        document.save()

    return JsonResponse({
        "success": True,
        "id": document.id,
        "document_type": document.document_type,
        "filename": document.file.name.split("/")[-1],
        "uploaded_at": document.uploaded_at.strftime("%d %b %Y %H:%M"),
    })


@login_required
@permission_required("crm.delete_document", raise_exception=True)
def document_delete(request, pk):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)

    document = get_object_or_404(Document, pk=pk)

    lead = get_visible_queryset(Lead, request.user).filter(pk=document.lead_id).first()
    if not lead:
        return JsonResponse({"error": "Access denied"}, status=403)

    with transaction.atomic():
        document.delete()

    return JsonResponse({
        "success": True,
        "id": pk,
    })