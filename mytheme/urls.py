"""mytheme URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path       
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from crm.views import CustomLoginView,myProfile
handler403 = 'crm.views.custom_permission_denied_view'
from crm.views import field_access_control_view
from .forms import LoginForm, MyChangePasswordForm,MypasswordResetForm,MySetPasswordForm,MyChangePasswordForm

#admin.site.site_header = "LPL Admin"
#admin.site.site_title = "LPL Admin Portal"
#admin.site.index_title = "Welcome to LPL CRM Portal"

urlpatterns = [
    path('admin/field-access-control/', field_access_control_view, name='field_access_control'),
    path('admin/', admin.site.urls),
    path('crm/', include('crm.urls')),
    path('',include('notifications.urls')),
    
    path('tinymce/', include('tinymce.urls')),
    path("reports/", include("reports.urls", namespace="reports")),

    # Login Urls by Ashutosh
    path('',CustomLoginView.as_view(template_name='login.html',
        authentication_form=LoginForm),name ='login'),
    
    path('login/',CustomLoginView.as_view(template_name='login.html',
        authentication_form=LoginForm),name ='login'),
    
    # Change Password urls
    path('changepassword/', auth_views.PasswordChangeView.as_view(template_name='crm/user/change_password.html',
        form_class=MyChangePasswordForm,success_url='/passwordchangedone'),name='changepassword'),
    
    path('passwordchangedone/', auth_views.PasswordChangeDoneView.as_view(
        template_name='crm/user/password_changedone.html' ), name='passwordchangedone'), 
    
    
   # Forget password section Start by Ashtosh Singh
    path('password-reset',auth_views.PasswordResetView.
        as_view(template_name='ForgotPassword/password_reset.html',
        form_class=MypasswordResetForm),name='password_reset'),
    
    path('password-reset/done/',auth_views.PasswordResetDoneView.
        as_view(template_name='ForgotPassword/password_reset_done.html',
        ),name='password_reset_done'),
    
    path('password-reset-confirm/<uidb64>/<token>/',auth_views.PasswordResetConfirmView.
        as_view(template_name='ForgotPassword/password_reset_confirm.html',form_class=MySetPasswordForm
        ),name='password_reset_confirm'),
    
    path('password-reset-complete',auth_views.PasswordResetCompleteView.
        as_view(template_name='ForgotPassword/password_reset_complete.html',
        ),name='password_reset_complete'),
    
    #####################  Forget password section End ###########################
    
    path('logout/',auth_views.LogoutView.as_view(next_page='login'),name='logout'),
    
    path('my-profile',myProfile, name="my_profile"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
