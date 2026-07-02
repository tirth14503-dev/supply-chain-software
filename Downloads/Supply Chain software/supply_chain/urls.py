from django.contrib import admin
from django.urls import path, include
from dashboard.views import dashboard

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', dashboard, name='dashboard'),
    path('inventory/', include('inventory.urls')),
    path('suppliers/', include('suppliers.urls')),
    path('orders/', include('orders.urls')),
    path('shipments/', include('shipments.urls')),
    path('ai/', include('ai_insights.urls')),
]
