from django.db import models
from orders.models import SalesOrder, PurchaseOrder


class Shipment(models.Model):
    STATUS = [
        ('pending', 'Pending'),
        ('in_transit', 'In Transit'),
        ('out_for_delivery', 'Out for Delivery'),
        ('delivered', 'Delivered'),
        ('returned', 'Returned'),
        ('lost', 'Lost'),
    ]

    TYPE = [('inbound', 'Inbound'), ('outbound', 'Outbound')]

    tracking_number = models.CharField(max_length=100, unique=True)
    shipment_type = models.CharField(max_length=20, choices=TYPE)
    sales_order = models.OneToOneField(SalesOrder, on_delete=models.SET_NULL, null=True, blank=True)
    purchase_order = models.OneToOneField(PurchaseOrder, on_delete=models.SET_NULL, null=True, blank=True)
    carrier = models.CharField(max_length=100)
    status = models.CharField(max_length=30, choices=STATUS, default='pending')
    origin = models.CharField(max_length=300)
    destination = models.CharField(max_length=300)
    ship_date = models.DateField(null=True, blank=True)
    estimated_delivery = models.DateField(null=True, blank=True)
    actual_delivery = models.DateField(null=True, blank=True)
    weight_kg = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.tracking_number
