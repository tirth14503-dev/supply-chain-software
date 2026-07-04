from django.contrib import admin
from .models import Category, Warehouse, Product, Stock, StockMovement

admin.site.register(Category)
admin.site.register(Warehouse)
admin.site.register(Product)
admin.site.register(Stock)


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'product', 'warehouse', 'movement_type', 'quantity', 'reference_type', 'reference_number', 'created_by')
    list_filter = ('movement_type', 'reference_type', 'warehouse')
    search_fields = ('product__name', 'reference_number', 'notes')
    readonly_fields = ('created_at',)
