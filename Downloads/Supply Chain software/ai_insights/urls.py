from django.urls import path
from . import views

urlpatterns = [
    path('', views.ai_dashboard, name='ai_dashboard'),
    path('demand-forecast/', views.demand_forecast, name='ai_demand_forecast'),
    path('smart-reorder/', views.smart_reorder, name='ai_smart_reorder'),
    path('supplier-risk/', views.supplier_risk, name='ai_supplier_risk'),
    path('anomaly-detection/', views.anomaly_detection, name='ai_anomaly_detection'),
    path('delay-predictor/', views.delay_predictor, name='ai_delay_predictor'),
]
