from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = 'categories'

    def __str__(self):
        return self.name


class Warehouse(models.Model):
    name = models.CharField(max_length=200)
    location = models.CharField(max_length=300)
    capacity = models.PositiveIntegerField(default=0)
    manager = models.CharField(max_length=150, blank=True)

    def __str__(self):
        return self.name

    @property
    def total_stock(self):
        return sum(s.quantity for s in self.stock_set.all())


class Product(models.Model):
    sku = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.TextField(blank=True)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    unit = models.CharField(max_length=30, default='pcs')
    reorder_point = models.PositiveIntegerField(default=10)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.sku} – {self.name}'

    @property
    def total_stock(self):
        return sum(s.quantity for s in self.stock_set.all())

    @property
    def is_low_stock(self):
        return self.total_stock <= self.reorder_point


class Stock(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('product', 'warehouse')

    def __str__(self):
        return f'{self.product.name} @ {self.warehouse.name}: {self.quantity}'
