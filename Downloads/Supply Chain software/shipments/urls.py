from django.urls import path
from . import views

urlpatterns = [
    path('', views.shipment_list, name='shipment_list'),
    path('new/', views.shipment_create, name='shipment_create'),
    path('<int:pk>/', views.shipment_detail, name='shipment_detail'),
    path('<int:pk>/status/', views.shipment_update_status, name='shipment_update_status'),
]
