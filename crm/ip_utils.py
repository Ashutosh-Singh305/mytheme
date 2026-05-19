import ipaddress

from crm.models import IPRange

def get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")

    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()

    return request.META.get("REMOTE_ADDR")


def is_ip_in_range(ip, start_ip, end_ip):
    try:
        ip_obj = ipaddress.ip_address(ip)
        return ipaddress.ip_address(start_ip) <= ip_obj <= ipaddress.ip_address(end_ip)
    except ValueError:
        return False



def is_login_ip_allowed(user, ip):
    # IP bypass
    if user.is_superuser or user.has_perm("crm.can_bypass_ip_restriction"):
        return True


    ranges = IPRange.objects.filter(is_active=True)
    # Strict mode (like Salesforce Profile Login IP)
    if not ranges.exists():
        return False

    for r in ranges:
        if is_ip_in_range(ip, r.start_ip, r.end_ip):
            return True

    return False