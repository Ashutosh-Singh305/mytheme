# crm/admin_views.py

from django.shortcuts import render,redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.timezone import make_aware,now
from django.core.paginator import Paginator
from datetime import datetime
from django.contrib.auth.models import User
import requests
from crm import models
from django.db.models import Q
from crm.models import Lead
from crm.utils import get_model_diff, get_visible_queryset,apply_audit_logic
from django.http import Http404, HttpResponse
import pandas as pd
from django.apps import apps
from django.contrib import messages
from django import forms
from django.urls import reverse
from django.db import models
from django.core.paginator import Paginator
import csv
from crm.choices import CUSTOM_FK_MATCH_FIELDS
from django.http import JsonResponse

# --- NEW: safe datetime alias + helpers for date parsing ---
import datetime as pydt
from django.db.models import DateField, DateTimeField, ForeignKey as DJForeignKey  # note: keep local alias

def _parse_excel_serial(n):
    """Excel serial date → date (Windows epoch 1899-12-30)."""
    try:
        n = float(n)
    except Exception:
        return None
    base = pydt.date(1899, 12, 30)
    return base + pydt.timedelta(days=int(n))

def parse_date_like(value):
    """
    Coerce many date forms to `date`:
    - '14-10-2025', '14/10/2025', '14.10.2025'
    - '14-10-25' (assume 2000–2099)
    - Excel serials like 45678
    - ISO '2025-10-14'
    """
    if value is None:
        return None

    v = str(value).strip()
    if not v:
        return None

    # Excel serials (pure number, reasonable range)
    if v.isdigit() and 20000 <= int(v) <= 60000:
        return _parse_excel_serial(v)

    fmts = [
        "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y",
        "%d-%m-%y", "%d/%m/%y", "%Y-%m-%d",
    ]
    for fmt in fmts:
        try:
            dt = pydt.datetime.strptime(v, fmt)
            # two-digit year -> assume 2000–2099
            if "%y" in fmt and dt.year < 100:
                dt = dt.replace(year=dt.year + 2000)
            return dt.date()
        except ValueError:
            pass

    # Last resort: ISO-ish
    try:
        return pydt.datetime.fromisoformat(v).date()
    except Exception:
        pass

    raise ValueError(f"Invalid date: {value!r}. Expected formats like DD-MM-YYYY.")

def _get_date_field_names(model):
    """Return (date_field_names, datetime_field_names) on a model."""
    date_fields, datetime_fields = [], []
    for f in model._meta.get_fields():
        if isinstance(f, DateTimeField):
            datetime_fields.append(f.name)
        elif isinstance(f, DateField):
            date_fields.append(f.name)
    return date_fields, datetime_fields

def normalize_instances_for_bulk_create(model, instances):
    """
    Given model instances, coerce any DateField/DateTimeField string/number
    into real date/datetime. Returns (fixed_instances, errors).
    """
    date_fields, datetime_fields = _get_date_field_names(model)
    fixed, errors = [], []
    for idx, obj in enumerate(instances, start=1):
        try:
            # Dates
            for fname in date_fields:
                raw = getattr(obj, fname, None)
                if isinstance(raw, (str, int, float)):
                    setattr(obj, fname, parse_date_like(raw))

            # DateTimes: if only a date-like value provided, set to midnight
            for fname in datetime_fields:
                raw = getattr(obj, fname, None)
                if isinstance(raw, (str, int, float)):
                    d = parse_date_like(raw)
                    if d is not None:
                        setattr(obj, fname, pydt.datetime(d.year, d.month, d.day))
            fixed.append(obj)
        except Exception as e:
            errors.append((idx, str(e)))
    return fixed, errors
# --- END NEW HELPERS ---


@staff_member_required
def user_activity_report(request):
    """
    View to display user activity (audit trail) on Lead records.
    - No data shown by default
    - On filter submit, shows paginated data with export option
    - Respects user-based visibility using get_visible_queryset()
    """

    # Get filters from request
    user_id = request.GET.get("user")
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")
    action = request.GET.get("action")
    export = request.GET.get("export")

    history_qs = Lead.history.none()  # Show nothing by default

    # Only run filter logic if at least one filter is applied
    if user_id or  start_date or end_date or action:
        # Get visible leads for current user
        visible_leads_qs = get_visible_queryset(Lead, request.user, owner_field="assigned_to")
        allowed_lead_ids = visible_leads_qs.values_list("id", flat=True)

        # Build queryset from history with access control
        history_qs = Lead.history.filter(id__in=allowed_lead_ids).select_related("history_user")

        # Apply filters
        if user_id and user_id != "all":
            history_qs = history_qs.filter(history_user_id=int(user_id))
        if start_date:
            start_dt = make_aware(datetime.strptime(start_date, "%Y-%m-%d"))
            history_qs = history_qs.filter(history_date__gte=start_dt)
        if end_date:
            end_dt = make_aware(datetime.strptime(end_date, "%Y-%m-%d"))
            history_qs = history_qs.filter(history_date__lte=end_dt)
        if action:
            history_qs = history_qs.filter(history_type=action)

        # If Excel export requested, handle it now
        if export == "excel":
            return export_audit_excel(request, history_qs.order_by("-history_date"))

        # Paginate results (e.g., 50 per page)
        paginator = Paginator(history_qs.order_by("-history_date"), 50)
        page_number = request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        history_list = []
        for item in page_obj:
            try:
                prev = item.prev_record
                diff = get_model_diff(prev.instance, item.instance) if prev else {}
            except Exception:
                diff = {}

            status_display = getattr(item.instance, "get_status_display", lambda: None)()
            history_list.append({
                "record": item,
                "diff": diff,
                "status_label": status_display,
            })
    else:
        # No filter submitted, so no queryset and empty page_obj
        page_obj = None
        history_list = []

    context = {
        "history_list": history_list,
        "page_obj": page_obj,
        "users": User.objects.all(),
        "filter_user": user_id,
        "filter_start": start_date,
        "filter_end": end_date,
        "filter_action": action,
    }
    return render(request, "admin/crm/report/user_activity_report.html", context)

import re

# 🔴 Excel-safe sanitizer
ILLEGAL_CHARACTERS_RE = re.compile(r'[\x00-\x08\x0B-\x0C\x0E-\x1F]')

def clean_excel_value(value):
    if isinstance(value, str):
        return ILLEGAL_CHARACTERS_RE.sub('', value)
    return value


def export_audit_excel(request, queryset):
    data = []

    for item in queryset:
        try:
            prev = item.prev_record
            diff = get_model_diff(prev.instance, item.instance) if prev else {}
        except Exception:
            diff = {}

        data.append({
            "Date": item.history_date.strftime('%Y-%m-%d %H:%M:%S'),
            "User": item.history_user.get_full_name() if item.history_user else "",
            "Action": {"+": "Created", "~": "Updated", "-": "Deleted"}.get(item.history_type, item.history_type),
            "Lead": item.name,
            "Mobile Number": item.mobile_number,
            "Status": item.get_status_display(),
            "Changes": "; ".join([f"{k}: {v[0]} → {v[1]}" for k, v in diff.items()])
        })

    df = pd.DataFrame(data)
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    filename = f"user_activity_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    response['Content-Disposition'] = f'attachment; filename={filename}'
    with pd.ExcelWriter(response, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    return response

####### Code for generic data upload feature #########
# crm/admin_views.py
from django.db.models import ForeignKey

class UploadForm(forms.Form):
    model_name = forms.ChoiceField(
        label="Model to Upload",
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )

    file = forms.FileField(
        label="Excel File",
        widget=forms.ClearableFileInput(attrs={
            'class': 'form-control'
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        crm_models = apps.get_app_config('crm').get_models()
        choices = [(model.__name__, model.__name__) for model in crm_models if not model._meta.abstract]
        self.fields['model_name'].choices = choices


@staff_member_required
def data_upload_view(request):
    if request.method == "POST":
        form = UploadForm(request.POST, request.FILES)
        if form.is_valid():
            model_name = form.cleaned_data['model_name']
            file = request.FILES['file']
            try:
                df = pd.read_excel(file)

                # Convert all values safely
                def clean_value(x):

                    # Handle NaN / NaT
                    if pd.isna(x):
                        return None

                    # Handle Timestamp
                    if isinstance(x, pd.Timestamp):
                        return x.strftime("%Y-%m-%d %H:%M:%S")

                    return x

                df = df.map(clean_value)

                request.session['upload_data'] = df.to_dict(orient='records')
                request.session['model_name'] = model_name

                return redirect('crm-data-upload-mapping')

            except Exception as e:
                messages.error(request, f"Error reading Excel: {e}")

    else:
        form = UploadForm()

    return render(request, "admin/data_upload.html", {"form": form})

class MappingForm(forms.Form):
    """
    Dynamically builds a form that maps Excel columns to model fields.
    - Shows verbose_name for clarity
    - Ensures required fields are mapped
    """

    def __init__(self, excel_columns, model, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.model = model
        self.model_fields = [f for f in model._meta.fields]
        self.required_fields = [f for f in self.model_fields if not f.blank and not f.null and f.name != 'id']

        # Mapping of field name to verbose name
        self.verbose_lookup = {f.name: f.verbose_name for f in self.model_fields}

        # Dropdown choices for the mapping form
        choices = [('', '---')]
        for f in self.model_fields:
            label = f"{f.verbose_name} (FK)" if f.is_relation and f.many_to_one else f.verbose_name
            choices.append((f.name, label))

        # Utility function to normalize strings
        def normalize(s):
            return str(s).strip().lower().replace(" ", "").replace("_", "")

        # Auto-map Excel column headers to model fields (fuzzy match)
        auto_map = {}
        for col in excel_columns:
            for f in self.model_fields:
                if normalize(col) == normalize(f.name) or normalize(col) == normalize(f.verbose_name):
                    auto_map[col] = f.name
                    break

        # Create form fields for each Excel column
        for col in excel_columns:
            self.fields[col] = forms.ChoiceField(
                choices=choices,
                required=False,
                label=f'Map Excel column: "{col}"',
                initial=auto_map.get(col, '')
            )

    def clean(self):
        cleaned_data = super().clean()
        mapped_fields = list(filter(None, cleaned_data.values()))

        # ✅ Detect if ID is mapped (means UPDATE mode)
        is_update = 'id' in mapped_fields

        missing_fields = []

        # ✅ Only enforce required fields in CREATE mode
        if not is_update:
            for field in self.required_fields:
                if field.name not in mapped_fields:
                    missing_fields.append(field.name)

        if missing_fields:
            missing_labels = [self.verbose_lookup[f] for f in missing_fields]
            raise forms.ValidationError(
                f"The following required fields are not mapped: {', '.join(missing_labels)}"
            )

        return cleaned_data

@staff_member_required
def data_upload_mapping_view(request):
    data_dict = request.session.get('upload_data')
    model_name = request.session.get('model_name')

    if not data_dict or not model_name:
        messages.error(request, "Session expired. Please upload the file again.")
        return redirect('crm-data-upload')

    df = pd.DataFrame(data_dict)
    model = apps.get_model('crm', model_name)

    if request.method == "POST":
        form = MappingForm(df.columns, model, request.POST)
        if form.is_valid():
            mappings = form.cleaned_data

            created_objs = []
            update_objs = []
            skipped_rows = []
            created = updated = skipped = 0

            # 🔥 Track fields dynamically for update
            update_field_set = set()

            for index, row in df.iterrows():
                if row.isnull().all():
                    continue

                obj_data = {}
                obj_id = None

                try:
                    for excel_col, model_field in mappings.items():
                        if not model_field:
                            continue

                        value = row.get(excel_col)

                        if model_field.lower() == 'id':
                            if not pd.isna(value):
                                obj_id = int(value)
                            continue

                        if pd.isna(value):
                            continue

                        field_obj = model._meta.get_field(model_field)

                        # FK handling
                        if isinstance(field_obj, ForeignKey):
                            rel_model = field_obj.remote_field.model
                            rel_obj = None
                            val = str(value).strip()

                            if val.isdigit():
                                rel_obj = rel_model.objects.filter(id=int(val)).first()

                            if not rel_obj:
                                rel_model_label = rel_model._meta.label
                                match_fields = CUSTOM_FK_MATCH_FIELDS.get(rel_model_label, [])

                                query = Q()
                                for field in match_fields:
                                    query |= Q(**{f"{field}__iexact": val})

                                if query:
                                    rel_obj = rel_model.objects.filter(query).first()

                            if rel_obj:
                                obj_data[model_field] = rel_obj
                            else:
                                raise ValueError(f"No match for FK '{model_field}': '{value}'")

                        else:
                            if field_obj.choices:
                                value = next(
                                    (k for k, v in field_obj.choices if v.lower() == str(value).strip().lower()),
                                    value
                                )

                            if isinstance(field_obj, (DateField, DateTimeField)):
                                d = parse_date_like(value)
                                obj_data[model_field] = (
                                    pydt.datetime(d.year, d.month, d.day) if isinstance(field_obj, DateTimeField) and d else d
                                )
                            else:
                                obj_data[model_field] = value

                    # ================= UPDATE =================
                    if obj_id:
                        instance = model.objects.filter(id=obj_id).first()

                        if not instance:
                            raise ValueError(f"Record with ID {obj_id} not found")

                        for k, v in obj_data.items():
                            setattr(instance, k, v)

                        apply_audit_logic(instance, request, is_create=False)

                        update_objs.append(instance)

                        # Track only changed fields
                        update_field_set.update(obj_data.keys())

                        updated += 1
                        continue

                    # ================= CREATE =================
                    instance = model(**obj_data)

                    apply_audit_logic(instance, request, is_create=True)

                    created_objs.append(instance)
                    created += 1

                except Exception as e:
                    skipped += 1
                    skipped_rows.append((f"Row {int(index) + 2}", str(e)))

            # Normalize dates
            if created_objs:
                created_objs, create_errors = normalize_instances_for_bulk_create(model, created_objs)
                for idx, msg in create_errors:
                    skipped_rows.append((f"Row (create) #{idx}", msg))
                    skipped += 1

            if update_objs:
                update_objs, update_errors = normalize_instances_for_bulk_create(model, update_objs)
                for idx, msg in update_errors:
                    skipped_rows.append((f"Row (update) #{idx}", msg))
                    skipped += 1

            # 🔥 BATCH SIZE (critical for performance)
            BATCH_SIZE = 200

            # Bulk create (batched)
            if created_objs:
                for i in range(0, len(created_objs), BATCH_SIZE):
                    model.objects.bulk_create(created_objs[i:i+BATCH_SIZE])

            # Bulk update (batched + optimized)
            if update_objs:
                update_fields = list(update_field_set) + ['modified_by', 'modified_at', 'assigned_to']

                for i in range(0, len(update_objs), BATCH_SIZE):
                    batch = update_objs[i:i+BATCH_SIZE]
                    model.objects.bulk_update(batch, update_fields)

            return render(request, "admin/data_summary.html", {
                "created": created,
                "updated": updated,
                "skipped": skipped,
                "skipped_rows": skipped_rows,
            })

    else:
        form = MappingForm(df.columns, model)

    return render(request, "admin/data_mapping.html", {
        "form": form,
    })

########### Logic for Custom report view #######
@staff_member_required
def select_model_view(request):
    from django.apps import apps

    if request.method == "POST":
        selected_model = request.POST.get("model")
        request.session["selected_model"] = selected_model
        return redirect(reverse("select_report_fields"))

    models_all = apps.get_models()
    model_choices = [
        (f"{model._meta.app_label}.{model.__name__}", model._meta.verbose_name.title())
        for model in models_all
        if model._meta.app_label == "crm"
    ]
    return render(request, "admin/report_builder/select_model.html", {"model_choices": model_choices})


@staff_member_required
def select_fields_view(request):
    selected_model_path = request.session.get("selected_model")

    if not selected_model_path:
        return redirect("select_report_model")

    try:
        app_label, model_name = selected_model_path.split(".")
        model = apps.get_model(app_label, model_name)
    except (ValueError, LookupError):
        raise Http404("Invalid model selected.")

    fields = [
        (field.name, field.verbose_name.title() if hasattr(field, 'verbose_name') else field.name.title())
        for field in model._meta.get_fields()
        if not field.many_to_many and not field.one_to_many
    ]

    if request.method == "POST":
        selected_fields = request.POST.getlist("fields")
        # ✅ Save under correct and consistent key
        request.session["selected_fields"] = selected_fields
        return redirect("select_report_filters")

    context = {
        "model_name": model._meta.verbose_name.title(),
        "fields": fields,
    }
    return render(request, "admin/report_builder/select_fields.html", context)


@staff_member_required
def add_filters_view(request):
    model_path = request.session.get('selected_model')
    selected_fields = request.session.get('selected_fields', [])

    if not model_path:
        return redirect('select_report_model')

    app_label, model_name = model_path.split(".")
    model = apps.get_model(app_label, model_name)

    usable_fields = [
        f for f in model._meta.fields
        if not f.many_to_many and not f.auto_created
    ]

    field_choices = [('', '--- Select Field ---')] + [(f.name, f.verbose_name.title()) for f in usable_fields]

    FILTER_CHOICES = [
        ('exact', 'Equals'),
        ('iexact', 'Equals (case-insensitive)'),
        ('contains', 'Contains'),
        ('icontains', 'Contains (case-insensitive)'),
        ('gt', 'Greater than'),
        ('lt', 'Less than'),
        ('gte', 'Greater than or equal to'),
        ('lte', 'Less than or equal to'),
        ('isnull', 'Is null'),
        ('in', 'In (comma separated values)'),
        ('notin', 'Not in (comma separated values)'),
    ]

    class FilterForm(forms.Form):
        field = forms.ChoiceField(choices=field_choices, label="Field", required=False)
        condition = forms.ChoiceField(choices=FILTER_CHOICES, label="Condition")
        value = forms.CharField(required=False, label="Value")

    if request.method == "GET" and request.GET.get("reset") == "1":
        request.session['report_filters'] = []

    filters = request.session.get('report_filters', [])

    if request.method == "POST":
        form = FilterForm(request.POST)
        if form.is_valid():
            field = form.cleaned_data.get("field")
            condition = form.cleaned_data.get("condition")
            value = form.cleaned_data.get("value")

            if field:
                filters.append({
                    "field": field,
                    "condition": condition,
                    "value": value,
                })
                request.session['report_filters'] = filters

            if "add_another" in request.POST:
                return redirect('select_report_filters')
            else:
                return redirect('generate_report')
    else:
        form = FilterForm()

    return render(request, 'admin/report_builder/add_filters.html', {
        'form': form,
        'filters': filters
    })

@staff_member_required
def generate_report_view(request):
    model_name = request.session.get('selected_model')
    selected_fields = request.session.get('selected_fields', [])
    applied_filters = request.session.get('report_filters', [])

    if not model_name or not selected_fields:
        return render(request, 'admin/report_builder/generate_report.html', {
            'columns': [],
            'data': [],
            'model_name': model_name,
            'filters': applied_filters,
        })

    app_label, model_class_name = model_name.split('.')
    model = apps.get_model(app_label, model_class_name)
    queryset = model.objects.all()

    # Apply filters (your existing logic)
    for f in applied_filters:
        field_name = f.get('field')
        condition = f.get('condition')
        value = f.get('value')

        if not field_name or not condition:
            continue

        try:
            field_obj = model._meta.get_field(field_name)
            filter_key = f"{field_name}__{condition}"

            if isinstance(field_obj, (models.DateField, models.DateTimeField)):
                if value:
                    value = datetime.strptime(value, "%Y-%m-%d").date()
                else:
                    continue
            elif isinstance(field_obj, models.BooleanField):
                value = value.lower() in ["true", "1", "yes"]
            elif isinstance(field_obj, models.IntegerField):
                value = int(value)
            elif isinstance(field_obj, models.FloatField):
                value = float(value)
            elif isinstance(field_obj, models.ForeignKey):
                related_model = field_obj.remote_field.model
                if not value:
                    continue
                value_obj = related_model.objects.filter(pk=value).first()
                if not value_obj and related_model._meta.model_name == 'user':
                    value_obj = related_model.objects.filter(username__iexact=value).first()
                if value_obj:
                    value = value_obj.pk
                else:
                    continue
            if condition == "in" or condition == "notin":
                value_list = [v.strip() for v in value.split(",") if v.strip()]
                if isinstance(field_obj, (models.IntegerField, models.FloatField)):
                    value_list = [int(v) for v in value_list if v.isdigit()]
                if condition == "notin":
                    queryset = queryset.exclude(**{f"{field_name}__in": value_list})
                    continue
                else:
                    queryset = queryset.filter(**{f"{field_name}__in": value_list})
                    continue

            queryset = queryset.filter(**{filter_key: value})
        except Exception as e:
            print(f"Skipping filter {f} due to error: {e}")
            continue

    # Handle sorting
    sort_field = request.GET.get('sort')
    sort_order = request.GET.get('order', 'asc')

    if sort_field in selected_fields:
        if sort_order == 'desc':
            queryset = queryset.order_by(f'-{sort_field}')
        else:
            queryset = queryset.order_by(sort_field)

    # Pagination
    paginator = Paginator(queryset.values(*selected_fields), 25)  # 25 records per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    columns = selected_fields
    data = page_obj.object_list

    return render(request, 'admin/report_builder/generate_report.html', {
        'columns': columns,
        'data': data,
        'model_name': model_class_name,
        'filters': applied_filters,
        'page_obj': page_obj,
        'sort_field': sort_field,
        'sort_order': sort_order,
    })


@staff_member_required
def export_report_csv_view(request):
    model_path = request.session.get('selected_model')
    selected_fields = request.session.get('selected_fields', [])
    filters = request.session.get('report_filters', [])

    if not model_path or not selected_fields:
        return HttpResponse("No report configuration found.", status=400)

    app_label, model_name = model_path.split(".")
    model = apps.get_model(app_label, model_name)

    filter_kwargs = {}
    not_in_filters = []

    for f in filters:
        field = f.get('field')
        condition = f.get('condition')
        val = f.get('value')

        # Skip if no field or empty val except for isnull
        if not field:
            continue
        if (val is None or val == '') and condition != 'isnull':
            continue

        if condition == 'isnull':
            val_bool = val.lower() in ['true', '1', 'yes']
            filter_kwargs[f"{field}__isnull"] = val_bool
        elif condition in ['in', 'notin']:
            val_list = [v.strip() for v in val.split(',') if v.strip()]
            if not val_list:
                continue
            if condition == 'notin':
                # Store notin filters to apply with exclude later
                not_in_filters.append((field, val_list))
            else:
                filter_kwargs[f"{field}__in"] = val_list
        else:
            try:
                field_obj = model._meta.get_field(field)
                if isinstance(field_obj, models.IntegerField):
                    val = int(val)
                elif isinstance(field_obj, models.FloatField):
                    val = float(val)
                elif isinstance(field_obj, models.BooleanField):
                    val = val.lower() in ['true', '1', 'yes']
                filter_kwargs[f"{field}__{condition}"] = val
            except (ValueError, TypeError, models.FieldDoesNotExist):
                # Skip invalid filter values or unknown fields
                continue

    # Apply filters to queryset
    queryset = model.objects.filter(**filter_kwargs)

    # Apply 'notin' exclusions
    for field, val_list in not_in_filters:
        queryset = queryset.exclude(**{f"{field}__in": val_list})

    queryset = queryset.values(*selected_fields)

    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="report.csv"'
    writer = csv.writer(response)
    writer.writerow(selected_fields)
    for row in queryset:
        writer.writerow([row.get(field, '') for field in selected_fields])

    return response


def get_branch_name(request):
    ifsc = request.GET.get("ifsc")

    if not ifsc:
        return JsonResponse({"error": "IFSC required"}, status=400)

    try:
        url = f"https://ifsc.razorpay.com/{ifsc}"
        res = requests.get(url, timeout=5)

        if res.status_code == 200:
            data = res.json()
            return JsonResponse({
                "branch": data.get("BRANCH", ""),
            })
        else:
            return JsonResponse({"error": "Invalid IFSC"}, status=404)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)