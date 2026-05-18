from theme import views
from django.urls import path

urlpatterns = [
    path('', views.index, name='index'), 
    path('list/', views.list, name='list'),
]