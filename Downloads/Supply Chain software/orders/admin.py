from django.contrib import admin
from .models import PurchaseOrder, PurchaseOrderItem, SalesOrder, SalesOrderItem

admin.site.register(PurchaseOrder)
admin.site.register(PurchaseOrderItem)
admin.site.register(SalesOrder)
admin.site.register(SalesOrderItem)
