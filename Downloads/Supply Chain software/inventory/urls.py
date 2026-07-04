from django.urls import path
from . import views

urlpatterns = [
    path('products/', views.product_list, name='product_list'),
    path('products/new/', views.product_create, name='product_create'),
    path('products/<int:pk>/', views.product_detail, name='product_detail'),
    path('products/<int:pk>/edit/', views.product_edit, name='product_edit'),
    path('products/<int:pk>/delete/', views.product_delete, name='product_delete'),
    path('products/<int:product_pk>/stock/', views.stock_adjust, name='stock_adjust'),
    path('warehouses/', views.warehouse_list, name='warehouse_list'),
    path('warehouses/new/', views.warehouse_create, name='warehouse_create'),
    path('warehouses/<int:pk>/edit/', views.warehouse_edit, name='warehouse_edit'),
    path('ledger/', views.stock_ledger, name='stock_ledger'),
    path('scan/', views.barcode_scan, name='barcode_scan'),
    path('api/lookup/', views.product_lookup, name='product_lookup'),
    path('products/<int:pk>/barcode/', views.barcode_print, name='barcode_print'),
]
