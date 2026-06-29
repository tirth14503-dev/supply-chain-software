from django.contrib import admin
from .models import Category, Warehouse, Product, Stock

admin.site.register(Category)
admin.site.register(Warehouse)
admin.site.register(Product)
admin.site.register(Stock)
