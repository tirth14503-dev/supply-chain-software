from django.contrib import admin
from django.urls import path, include
from dashboard.views import dashboard, finance_report

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('', dashboard, name='dashboard'),
    path('inventory/', include('inventory.urls')),
    path('suppliers/', include('suppliers.urls')),
    path('orders/', include('orders.urls')),
    path('shipments/', include('shipments.urls')),
    path('ai/', include('ai_insights.urls')),
    path('finance/', finance_report, name='finance_report'),
]
