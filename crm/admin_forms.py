from django import forms
from .models import FieldAccessControl, Lead, LeadFollowUp
from crm.utils import get_visible_queryset

class RoleBasedAccessForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if not user or not hasattr(user, 'userprofile'):
            return

        role = user.userprofile.role
        model_name = self._meta.model.__name__
        access_controls = FieldAccessControl.objects.filter(model_name=model_name, role=role)

        viewable_fields = set(ac.field_name for ac in access_controls if ac.can_view)
        editable_fields = set(ac.field_name for ac in access_controls if ac.can_edit)

        for field in self.fields:
            if field not in viewable_fields:
                self.fields[field].widget = forms.HiddenInput()  # 🔒 hide field but don’t remove it

            elif field not in editable_fields:
                self.fields[field].disabled = True  # 🔒 show but disable

class _LeadChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        phone = obj.mobile_number or ""
        # Shown as: Lead Name ( Phone )
        return f"{obj.name} ({phone})".strip()

class LeadFollowUpAdminForm(forms.ModelForm):
    # Use a custom choice field so we can control the label
    lead = _LeadChoiceField(queryset=Lead.objects.none())

    class Meta:
        model = LeadFollowUp
        fields = "__all__"

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter the leads exactly as your record-access logic defines
        qs = get_visible_queryset(Lead, user, owner_field="assigned_to")
        self.fields["lead"].queryset = qs.order_by("name")
