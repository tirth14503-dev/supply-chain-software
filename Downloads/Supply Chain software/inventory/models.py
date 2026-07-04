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
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    unit = models.CharField(max_length=30, default='pcs')
    reorder_point = models.PositiveIntegerField(default=10)
    barcode = models.CharField(max_length=100, blank=True, default='', help_text='EAN/UPC barcode (leave blank to use SKU)')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.sku} – {self.name}'

    @property
    def total_stock(self):
        return sum(s.quantity for s in self.stock_set.all())

    @property
    def is_low_stock(self):
        return self.total_stock <= self.reorder_point

    @property
    def stock_value(self):
        return self.total_stock * float(self.unit_price)


class Stock(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('product', 'warehouse')

    def __str__(self):
        return f'{self.product.name} @ {self.warehouse.name}: {self.quantity}'


class StockMovement(models.Model):
    MOVEMENT_TYPE = [
        ('in', 'Stock In'),
        ('out', 'Stock Out'),
        ('adjustment', 'Adjustment'),
    ]
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='movements')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='movements')
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPE)
    quantity = models.IntegerField()  # positive = in, negative = out
    reference_type = models.CharField(max_length=50, blank=True)  # 'PO', 'SO', 'Manual'
    reference_number = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=100, blank=True, default='System')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        sign = '+' if self.quantity > 0 else ''
        return f'{sign}{self.quantity} {self.product.name} @ {self.warehouse.name}'
