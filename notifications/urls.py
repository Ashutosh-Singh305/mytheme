# notifications/urls.py
from django.urls import path
from .views import notification_list
from notifications import views

urlpatterns = [
    path("api/notifications/", notification_list, name="notification_list"),
    path("api/notifications/mark-all-read/", views.mark_all_notifications_read, name="mark_all_notifications_read"),
    path("api/notifications/read/<int:pk>/", views.mark_notification_read, name="notification_mark_read"),
]
