from django import  forms
from . import registry
from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import models


class BasicReportForm(forms.Form):
    name = forms.CharField(
        widget=forms.TextInput(attrs={"class": "form-control form-control-sm"}),
        required=True
    )
    
    model = forms.ChoiceField(
        choices=[],
        widget=forms.Select(attrs={"class": "form-select form-select-sm select2"})
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3})
    )

    view = forms.ChoiceField(
        choices=[
            ("tabular", "Tabular"),
            ("summary", "Summary"),
            ("matrix", "Matrix"),
        ],
        widget=forms.Select(attrs={"class": "form-select form-select-sm"})
    )

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)

        from django.apps import apps
        from . import registry

        choices = []
        for m in registry.list_models():
            app_label, model_name = m.split(".")
            model_class = apps.get_model(app_label, model_name)
            label = model_class._meta.verbose_name.title()
            choices.append((m, label))

        self.fields["model"].choices = choices

class SelectObjectForm(forms.Form):
    model = forms.ChoiceField(
        choices=[],
        widget=forms.Select(attrs={"class": "form-select-sm select2"})
    )

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)

        choices = []

        for m in registry.list_models():   # m = "crm.Bank"
            app_label, model_name = m.split(".")  # safe & correct

            model_class = apps.get_model(app_label, model_name)

            # Now we can use _meta safely
            label = model_class._meta.verbose_name.title()

            choices.append((m, label))

        self.fields["model"].choices = choices



class SelectTypeForm(forms.Form):
    view = forms.ChoiceField(
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
        choices=[
            ("tabular", "Tabular"),
            ("summary", "Summary (Grouped)"),
            ("matrix", "Matrix"),
        ]
    )


class SelectFieldsForm(forms.Form):
    fields = forms.MultipleChoiceField(
        choices=[],
        widget=forms.CheckboxSelectMultiple
    )

    def __init__(self, model_label, *a, **kw):
        super().__init__(*a, **kw)

        app_label, model_name = model_label.split(".")
        model = apps.get_model(app_label, model_name)

        choices = []
        for field_name in registry.list_fields(model_label):
            try:
                field = model._meta.get_field(field_name)
                label = field.verbose_name.title()
            except Exception:
                # fallback for non-model fields (computed fields)
                label = field_name.replace("_", " ").title()

            choices.append((field_name, label))

        self.fields["fields"].choices = choices


class GroupMeasureForm(forms.Form):
    """
    Clean, simple UI:
      - row_groups: checkboxes
      - col_groups: checkboxes (matrix only; harmless if unused)
      - fn: one function dropdown
      - field: one field dropdown (may be blank when fn == 'count')
    """

    row_groups = forms.MultipleChoiceField(
        choices=[], required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Row Groups"
    )
    col_groups = forms.MultipleChoiceField(
        choices=[], required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Column Groups"
    )

    fn = forms.ChoiceField(
        choices=[
            ("count", "Count"),
            ("sum", "Sum"),
            ("avg", "Average"),
            ("min", "Min"),
            ("max", "Max"),
        ],
        required=True,
        label="Measure Function",
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
    )

    field = forms.ChoiceField(
        choices=[], required=False,
        label="Field (optional for Count)",
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
    )

    def __init__(self, model_label, *a, **kw):
        super().__init__(*a, **kw)

        # Load the model class from "app.Model"
        app_label, model_name = model_label.split(".")
        model = apps.get_model(app_label, model_name)

        # list of raw field names
        fields = registry.list_fields(model_label)

        # Build choices with pretty labels
        group_choices = []
        field_choices = []

        for fname in fields:
            try:
                # Get real Django model field
                f = model._meta.get_field(fname)
                label = f.verbose_name.title()
            except Exception:
                # fallback (computed fields / synthetic fields)
                label = fname.replace("_", " ").title()

            group_choices.append((fname, label))
            field_choices.append((fname, label))

        # Set group choices
        self.fields["row_groups"].choices = group_choices
        self.fields["col_groups"].choices = group_choices

        # Set field dropdown choices
        self.fields["field"].choices = [("", "— All Rows —")] + field_choices

    def clean(self):
        cd = super().clean()
        fn = cd.get("fn")
        field = cd.get("field")

        # For count: field is optional → normalize to None
        if fn == "count":
            cd["field"] = field or None
        else:
            # Other functions require a field
            if not field:
                self.add_error("field", "Please select a field for this aggregate.")

        return cd


class ReportEditForm(forms.ModelForm):
    class Meta:
        from .models import Report
        model = Report
        fields = ["name", "limit", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control form-control-sm", "placeholder": "Report name"}),
            "limit": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

# By Ashutosh on 1 dec 2025
FILTER_CHOICES = [
    ('eq', 'Equals'),
    ('neq', 'Not Equals'),
    ('contains', 'Contains'),
    ('not_contains', 'Not Contains'),
    ('startswith', 'Starts With'),
    ('endswith', 'Ends With'),
    ('gt', 'Greater than'),
    ('lt', 'Less than'),
    ('gte', 'Greater than or equal to'),
    ('lte', 'Less than or equal to'),
    ('isnull', 'Is null'),
    ('in', 'In'),
    ('not_in', 'Not In'),

    # Date operators
    ('today', 'Today'),
    ('yesterday', 'Yesterday'),
    ('7_days', 'Last 7 days'),
    ('30_days', 'Last 30 days'),
    ('this_month', 'This month'),
    ('last_month', 'Last month'),
]



class FilterForm(forms.Form):
    field = forms.ChoiceField(
        choices=[], 
        label="Field", 
        required=False,
        widget=forms.Select(attrs={"class": "form-control select2", "id": "id_field"})
    )

    condition = forms.ChoiceField(
        choices=FILTER_CHOICES, 
        label="Condition",
        widget=forms.Select(attrs={"class": "form-control select2", "id": "id_condition"})
    )

    value = forms.CharField(required=False, widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        dynamic_field_choices = kwargs.pop("field_choices", [])
        self.model_label = kwargs.pop("model_label", None)   # 🔥 IMPORTANT
        super().__init__(*args, **kwargs)
        self.fields["field"].choices = dynamic_field_choices

    def clean(self):
        cleaned_data = super().clean()

        field_name = cleaned_data.get("field")
        condition = cleaned_data.get("condition")
        value = cleaned_data.get("value")

        if not field_name or not self.model_label:
            return cleaned_data

        # Resolve model + field
        try:
            app_label, model_name = self.model_label.split(".")
            model = apps.get_model(app_label, model_name)
            field = model._meta.get_field(field_name)
        except Exception:
            return cleaned_data

        # FK VALIDATION
        if isinstance(field, models.ForeignKey):

            allowed_fk_conditions = ("eq", "neq", "in", "not_in", "isnull")

            condition_label_map = dict(FILTER_CHOICES)

            if condition not in allowed_fk_conditions:
                allowed_labels = [
                    condition_label_map.get(c, c) for c in allowed_fk_conditions
                ]

                raise ValidationError(
                    f"Invalid condition '{condition_label_map.get(condition, condition)}' "
                    f"for {field.verbose_name.title()}. "
                    f"Only {', '.join(allowed_labels)} are allowed."
                )

            if condition != "isnull":
                if not value:
                    raise ValidationError(
                        f"{field.verbose_name.title()} requires valid ID(s)."
                    )

                values = [v.strip() for v in str(value).split(",") if v.strip()]

                for v in values:
                    if not v.isdigit():
                        raise ValidationError(
                            f"{field.verbose_name.title()} must be numeric ID(s)."
                        )

        # NUMERIC FIELD VALIDATION
        if isinstance(field, (models.IntegerField, models.BigIntegerField, models.FloatField, models.DecimalField)):

            if condition in ("eq", "neq", "gt", "lt", "gte", "lte", "in", "not_in"):

                if not value:
                    raise ValidationError(
                        f"{field.verbose_name.title()} requires a numeric value."
                    )

                values = [v.strip() for v in str(value).split(",") if v.strip()]

                for v in values:
                    try:
                        float(v)
                    except ValueError:
                        raise ValidationError(
                            f"{field.verbose_name.title()} must be numeric."
                        )

        return cleaned_data