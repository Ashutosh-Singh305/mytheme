# crm/backends.py

from django.contrib.auth.backends import ModelBackend
from crm.ip_utils import get_client_ip, is_login_ip_allowed


class IPRestrictedBackend(ModelBackend):

    def authenticate(self, request, username=None, password=None, **kwargs):
        user = super().authenticate(request, username=username, password=password)

        if user is None:
            return None

        ip = get_client_ip(request)

        # 🔥 Instead of raising exception → mark request
        if not is_login_ip_allowed(user, ip):
            if request:
                request.ip_blocked = True
                request.blocked_ip = ip
            return None  # deny authentication

        return user