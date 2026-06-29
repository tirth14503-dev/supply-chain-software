from django.db import models


class Supplier(models.Model):
    STATUS_CHOICES = [('active', 'Active'), ('inactive', 'Inactive'), ('blacklisted', 'Blacklisted')]

    name = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=150, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    country = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    payment_terms = models.CharField(max_length=100, blank=True)
    lead_time_days = models.PositiveIntegerField(default=7)
    rating = models.DecimalField(max_digits=3, decimal_places=1, default=5.0)
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return self.name
