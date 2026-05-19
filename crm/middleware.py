from django.core.exceptions import PermissionDenied
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse
from crm.ip_utils import get_client_ip, is_login_ip_allowed
class CRMNamespacePermissionMiddleware:
    """
    Blocks access to the CRM namespace unless the user
    has the global `can_access_crm` permission.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/crm/'):
            user = request.user

            # Allow unauthenticated users to hit login page
            if not user.is_authenticated:
                return self.get_response(request)

            if not user.has_perm('crm.can_access_crm'):
                raise PermissionDenied("You do not have access to CRM. Contact Administration.")

        return self.get_response(request)



class IPRestrictionMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        # ✅ Only check for authenticated users
        if request.user.is_authenticated:

            # Optional: skip admin login/logout endpoints
            if request.path.startswith("/admin/login"):
                return self.get_response(request)

            ip = get_client_ip(request)

            if not is_login_ip_allowed(request.user, ip):
                logout(request)
                raise PermissionDenied("Access denied. Your current network is not authorized. Please connect through an approved network or contact the administrator.")

        return self.get_response(request)