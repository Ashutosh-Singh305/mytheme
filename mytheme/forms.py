from django import forms
from django.contrib.auth.forms import AuthenticationForm,UsernameField,PasswordChangeForm,PasswordResetForm,SetPasswordForm
from django.contrib.auth.models import User
from django.utils.translation import gettext,gettext_lazy as _
from django.contrib.auth import password_validation


# Login By Ashutosh 

class LoginForm(AuthenticationForm):
    username =UsernameField(widget=forms.TextInput(attrs={'autofocus':True,'placeholder':'Username ',
        'class':'form-control mb-2'}))
    
    password = forms.CharField(label=_("Password"),strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete':'current-password','placeholder':'Enter Password',
        'class':'form-control mb-2'}))

class MyChangePasswordForm(PasswordChangeForm):
    old_password = forms.CharField(label=_("Old Password"), strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete':'current-password','autofocus':True,'class':'form-control'}))
    
    new_password1 = forms.CharField(label=_("New Password"), strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete':'new-password','class':'form-control'}),
        help_text=password_validation.password_validators_help_text_html())

    new_password2 = forms.CharField(label=_("Conform New Password"), strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete':'new-password','class':'form-control'}))

# Password Reset Form by ashutosh
class MypasswordResetForm(PasswordResetForm):
    
    email = forms.EmailField(
        label=_("Email"),
        max_length=254,
        widget=forms.EmailInput(attrs={"autocomplete": "email",'class':'form-control'}),
    )

class MySetPasswordForm(SetPasswordForm):
    new_password1 = forms.CharField(
        label=_("New password"),
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password",'class':'form-control'}),
        strip=False,
        help_text=password_validation.password_validators_help_text_html(),
    )
    new_password2 = forms.CharField(
        label=_("New password confirmation"),
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password",'class':'form-control'}),
    )
    