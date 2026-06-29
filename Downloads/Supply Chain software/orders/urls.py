from django.urls import path
from . import views

urlpatterns = [
    path('purchase/', views.po_list, name='po_list'),
    path('purchase/new/', views.po_create, name='po_create'),
    path('purchase/<int:pk>/', views.po_detail, name='po_detail'),
    path('purchase/<int:pk>/status/', views.po_update_status, name='po_update_status'),
    path('sales/', views.so_list, name='so_list'),
    path('sales/new/', views.so_create, name='so_create'),
    path('sales/<int:pk>/', views.so_detail, name='so_detail'),
    path('sales/<int:pk>/status/', views.so_update_status, name='so_update_status'),
]
