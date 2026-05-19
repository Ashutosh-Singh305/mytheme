from django.urls import path
from . import views
app_name = "reports"
urlpatterns = [
    path("", views.ReportListView.as_view(), name="list"),
    path("new/", views.report_wizard, name="new"),
    

    # MTD Report urls  created (exported from the app crm)  by Ashutosh on 3 oct 2025
    path('report-builder/mtd/', views.mtd_report_view, name='mtd_reports'),
    path("mtd/user/<int:user_id>/details/", views.mtd_user_detail_view, name="mtd_user_detail"),
    
    path("report-builder/mtd-wip/", views.mtd_wip_report_view, name="mtd_wip_report"),
    path("mtd-wip/lender/<int:lender_id>/details/", views.mtd_wip_lender_detail_view, name="mtd_lender_detail"),

    # path('report-builder/active-leads/', views.active_lead_report_view, name='active_lead_reports'),
   
    path(
        "ajax/users-by-assignment/",
        views.ajax_users_by_assignment_field,
        name="ajax_users_by_assignment_field",
    ),
   
    
    path("report-builder/lead-status-history/", views.lead_status_history, name="lead_status_history"),
    path("lead-status-history/api/", views.lead_status_history_api, name="lead_status_history_api"),
    
    # Always add the last
    path("<slug:slug>/detail/", views.ReportDetailView.as_view(), name="detail"),
    path("<slug:slug>/edit/", views.report_wizard, name="edit"),
    path("<slug:slug>/delete/", views.ReportDeleteView.as_view(), name="delete"),
    path("<slug:slug>/", views.run_report, name="run"),
    
    # Export CSV by Ashutosh on 1 dec 2025
    path("<slug:slug>/export/csv/", views.export_report_csv, name="report_export_csv"),
    
    path("<slug:slug>/api/", views.run_report_api, name="run_report_api"),

]
