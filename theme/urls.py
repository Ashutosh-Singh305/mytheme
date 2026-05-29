from theme import views
from django.urls import path

urlpatterns = [
    path('', views.index, name='index'), 
    path('topmenu/', views.topmenu, name='topmenu'),
    path('list/', views.list, name='list-theme'),
]