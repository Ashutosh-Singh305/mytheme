from django.urls import path
from crm import listview_views
from crm import generic_crud
from . import views,admin_views

urlpatterns = [
    # To auto fetch branch when IFSC code is saved in bank details form
    path("api/get-branch/", admin_views.get_branch_name, name="get_branch_name"),
    
    path('groups/', views.group_list, name='group-list'),
    path('groups/create/', views.group_create, name='group-create'),
    path('groups/<int:pk>/update/', views.group_update, name='group-update'),
    path('groups/<int:pk>/delete/', views.group_delete, name='group-delete'),
    
    # ip
    path('ip/list', views.ip_list, name='ip-list'),
    path('ip/create/', views.ip_create, name='ip-create'),
    path('ip/<int:pk>/edit/', views.ip_edit, name='ip-edit'),
    path('ip/<int:pk>/delete/', views.ip_delete, name='ip-delete'),
    path('ip/<int:pk>/details/', views.ip_detail, name='ip-detail'),
    
    # Authentication URLs
    path('users/new/', views.user_create, name='user-create'),
    path('users/all/view/', views.user_list, name='user-list'),
    path('users/<int:pk>/details/', views.user_detail, name='user-detail'),
    path('users/<int:pk>/edit/', views.user_edit, name='user-edit'),
    path('users/<int:pk>/delete/', views.user_delete, name='user-delete'),
    path('users/<int:pk>/password/', views.user_password_change, name='user-password-change'),
    # path('my-profile',views.myProfile, name="my_profile"),
    
    # UserProfile
    path('users-profile/list/view/', views.userprofile_list, name='user_profile_list'),
    
    # Dashboard URLs
    path('', views.tse_dashboard, name='tse_dashboard'),
    path('dashboard/', views.tse_dashboard, name='lead_dashboard'),
    
    path('tse-dashboard/', views.tse_dashboard, name='tse_dashboard'),
    path('card-tse-dashboard/', views.card_tse_dashboard, name='card_tse_dashboard'),
    path('api/create-lead/', views.create_lead_api, name='create_lead_api'),
    path('api/test-smartflo/', views.test_smartflo, name='test_smartflo'),
    path('hr-dashboard/', views.hr_dashboard, name='hr_dashboard'),
    # AJAX APIs
    path('lead/<int:lead_id>/', views.get_lead_detail),
    path('candidate/<int:candidate_id>/', views.get_candidate_detail),
    path('candidate/update/', views.update_candidate, name='update_candidate'),
    path('candidate/create/', views.create_candidate, name='create_candidate'),
    path('lead/update-full/', views.update_lead_full),
    
    ### Bulk Assignment ###
    path('bulk-assign/', views.bulk_assign_leads, name='bulk_assign'),
    path('assign-leads/', views.assign_leads, name='assign_leads'),

    
    # Lead Follow-Up URLs
    path('leadfollowups/', views.leadfollowup_list, name='leadfollowup_list'),
    path('leadfollowups/new/', views.leadfollowup_create, name='leadfollowup_create'),
    path('leadfollowups/<int:pk>/', views.leadfollowup_detail, name='leadfollowup_detail'),
    path('leadfollowups/<int:pk>/edit/', views.leadfollowup_update, name='leadfollowup_update'),
    path('leadfollowups/<int:pk>/delete/', views.leadfollowup_delete, name='leadfollowup_delete'),

    # Document URLs
    path('documents/', views.document_list, name='document_list'),
    path('documents/create/', views.document_create, name='document_create'),
    path('documents/<int:pk>/update/', views.document_update, name='document_update'),
    path('documents/<int:pk>/delete/', views.document_delete, name='document_delete'),

    
    
    path("welcome/",views.WelcomeView,name="welcome"),
    # path('contact/', views.contact, name='contact'),
    path('tools/upload/', views.upload_leads_view, name='crm_lead_upload'),
    path("reports/user-activity/", admin_views.user_activity_report, name="crm_user_activity"),
    
    # Data Upload (outside admin path)
    path('data-upload/', admin_views.data_upload_view, name="crm-data-upload"),
    path('data-upload/mapping/', admin_views.data_upload_mapping_view, name="crm-data-upload-mapping"),
    path('field-access-control/', views.field_access_control_view, name='field_access_control'),
    
    path("report-builder/select-model/", admin_views.select_model_view, name="select_report_model"),
    path('report-builder/select-fields/', admin_views.select_fields_view, name='select_report_fields'),
    path('report-builder/add-filters/', admin_views.add_filters_view, name='select_report_filters'),
    path('report-builder/generate-report/', admin_views.generate_report_view, name='generate_report'),
    path('report-builder/export-csv/', admin_views.export_report_csv_view, name='export_report_csv'),
    
    # List View URLs
    # path("<str:model_name>/listviews", listview_views.listview_home, name="listview_home"),
    path("filters/<int:pk>/delete/", listview_views.delete_listview, name="listview_delete"),
    path("new/<str:model_name>/filter", listview_views.listview_editor, name="listview_new"),
    path("filters/<int:pk>/edit/", listview_views.listview_editor, name="listview_edit"),

    # ListView Ajax Endpoints
    path("listviews/get-models/", listview_views.get_all_models, name="crm_get_models"),
    path("listviews/get-fields/", listview_views.get_model_fields, name="crm_get_model_fields"),
    path("listviews/get_fk_values/", listview_views.get_fk_values, name="crm_get_fk_values"),
    path("listviews/check-listview-name/", listview_views.check_listview_name, name="check_listview_name"),
    
    # Genric Crud Urls
    path("<str:model>/new/", generic_crud.generic_create_object, name="crm_object_create"),
    path("<str:model>/<int:pk>/", generic_crud.generic_detail_object, name="crm_object_detail"),
    path("<str:model>/<int:pk>/edit/", generic_crud.generic_update_object, name="crm_object_edit"),
    path('<str:model>/<int:pk>/delete/', generic_crud.generic_delete_object, name='crm_object_delete'),
    path(
        "objects/<str:model>/<int:pk>/history/",
        generic_crud.generic_object_history,
        name="crm_object_history",
    ),
    # Put Always at last
    path("<str:model_name>/", listview_views.listview_results, name="listview_results"),
]