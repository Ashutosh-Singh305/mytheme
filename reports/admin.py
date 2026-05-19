from django.contrib import admin
from crm.admin_base import BaseAuditAdmin
from reports.models import Report
# Register your models here.


@admin.register(Report)
class ReportAdmin(BaseAuditAdmin):
    list_display = ("name", "owner", "limit", "is_active")

    