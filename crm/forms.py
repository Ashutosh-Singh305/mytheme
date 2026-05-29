from django import forms
from .models import *
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User, Group
from django.contrib.auth.models import Group

class GroupForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter group name'}),
        }
class IPRangeForm(forms.ModelForm):
    class Meta:
        model = IPRange
        fields = ['start_ip', 'end_ip', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for name, field in self.fields.items():

            # Checkbox field
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({
                    'class': 'form-check-input'
                })

            # Normal input fields
            else:
                field.widget.attrs.update({
                    'class': 'form-control',
                    'placeholder': field.label
                })
        
# Registration Form
class UserRegistrationForm(UserCreationForm):
    first_name = forms.CharField(
        label='First Name',
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    last_name = forms.CharField(
        label='Last Name',
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )

    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )

    password2 = forms.CharField(
        label='Confirm Password (again)',
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )

    # ✅ NEW FIELDS
    is_active = forms.BooleanField(
        required=False,
        initial=True,
        label="Active"
    )

    is_staff = forms.BooleanField(
        required=False,
        label="Staff Status"
    )

    is_superuser = forms.BooleanField(
        required=False,
        label="Superuser Status"
    )
    
    date_joined = forms.DateTimeField(
        required=False,
        label='Date Joined',
        widget=forms.DateTimeInput(
            attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }
        )
    )
    # ✅ ADD THESE
    last_login = forms.DateTimeField(
        required=False,
        label='Last Login',
        widget=forms.DateTimeInput(
            attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }
        )
    )


    # ✅ MULTISELECT GROUP
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        required=False,
        label='Assign Groups',
        widget=forms.SelectMultiple(attrs={'class': 'form-control select2'})
    )

    class Meta:
        model = User
        fields = [
            'username', 'first_name', 'last_name', 'email',
            'password1', 'password2',
            'is_active', 'is_staff', 'is_superuser',
            'groups','date_joined','last_login'
        ]

        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already taken.")
        return email

     
class UpdateUserRegistration(forms.ModelForm):

    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )

    # ✅ STATUS FIELDS
    is_active = forms.BooleanField(required=False, label="Active")
    is_staff = forms.BooleanField(required=False, label="Staff Status")
    is_superuser = forms.BooleanField(required=False, label="Superuser Status")
    

    date_joined = forms.DateTimeField(
        required=False,
        label='Date Joined',
        input_formats=['%Y-%m-%dT%H:%M'],
        widget=forms.DateTimeInput(
            format='%Y-%m-%dT%H:%M',
            attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }
        )
    )
    
    # ✅ ADD THESE
    last_login = forms.DateTimeField(
        required=False,
        label='Last Login',
        input_formats=['%Y-%m-%dT%H:%M'],
        widget=forms.DateTimeInput(
            format='%Y-%m-%dT%H:%M',
            attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }
        )
    )
    # ✅ MULTI GROUP
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        required=False,
        label='Assign Groups',
        widget=forms.SelectMultiple(attrs={'class': 'form-control select2'})
    )
    
    first_name = forms.CharField(
        label='First Name',
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    last_name = forms.CharField(
        label='Last Name',
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = User
        fields = [
            'username', 'first_name', 'last_name', 'email',
            'is_active', 'is_staff', 'is_superuser',
            'groups','date_joined','last_login'
        ]

        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
        }

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = [
            'emp_code',
            'role',
            'manager',
            'branch'
        ]
        
        widgets = {
            'emp_code': forms.TextInput(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-control'}),
        }

class LeadForm(forms.ModelForm):
    class Meta:
        model = Lead
        fields = ['name', 'father_name', 'gender', 'marital_status', 'dob', 'mobile_number',
                  'alternate_number', 'email', 'pan', 'adhar_number', 'present_address', 'permanent_address']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)  # Get the user
        super(LeadForm, self).__init__(*args, **kwargs)

        if user:
            user_profile = UserProfile.objects.get(user=user)
            restricted_fields = FieldAccessControl.objects.filter(
                role=user_profile.role,
                model_name="Lead",
                can_view=False
            ).values_list('field_name', flat=True)

            for field in restricted_fields:
                self.fields.pop(field, None)  # Remove restricted fields
    


class LeadCSVUploadForm(forms.Form):
    file = forms.FileField(
        label="Select CSV or Excel (.xlsx) file",
        help_text="Upload a .csv or .xlsx file with lead data.",
        widget=forms.ClearableFileInput(attrs={"accept": ".csv, .xlsx"})
    )

class BankForm(forms.ModelForm):
    class Meta:
        model = Bank
        fields = [
            'name', 'code', 'contact_person', 'contact_email', 'contact_phone', 'address',
            'agreement_start_date', 'agreement_end_date', 'agreement_status',
            'agreement_document', 'products_offered', 'max_commission_percent', 'status'
        ]
        widgets = {
            'agreement_start_date': forms.DateInput(
                format='%Y-%m-%d', 
                attrs={'type': 'date'}
            ),
            'agreement_end_date': forms.DateInput(
                format='%Y-%m-%d', 
                attrs={'type': 'date'}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'
        # Also make sure initial values are formatted correctly
        self.fields['agreement_start_date'].input_formats = ['%Y-%m-%d']
        self.fields['agreement_end_date'].input_formats = ['%Y-%m-%d']

class LeadFollowUpForm(forms.ModelForm):
    class Meta:
        model = LeadFollowUp
        fields = ['lead', 'user', 'note', 'follow_up_date']
        widgets = {
            'follow_up_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'
        self.fields['lead'].widget.attrs['class'] += ' select2-single'
        self.fields['user'].widget.attrs['class'] += ' select2-single'



class ProductCategoryForm(forms.ModelForm):
    class Meta:
        model = ProductCategory
        fields = ['name', 'description', 'icon', 'image', 'is_active']
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            'product_category', 'name', 'description',
            'features', 'eligibility_criteria',
            'product_image', 'product_icon',
            'is_active', 'is_index'
        ]
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'
        self.fields['product_category'].widget.attrs['class'] += ' select2-single'