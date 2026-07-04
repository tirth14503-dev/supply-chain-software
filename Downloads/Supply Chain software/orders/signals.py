from django.db.models.signals import pre_save
from django.dispatch import receiver
from .models import PurchaseOrder, SalesOrder
from inventory.models import Stock, StockMovement


@receiver(pre_save, sender=PurchaseOrder)
def po_received_update_stock(sender, instance, **kwargs):
    """When a PO moves to 'received', add items to stock and log each movement."""
    if not instance.pk:
        return
    try:
        old = PurchaseOrder.objects.get(pk=instance.pk)
    except PurchaseOrder.DoesNotExist:
        return
    if old.status == 'received' or instance.status != 'received':
        return
    for item in instance.items.select_related('product').all():
        stock, _ = Stock.objects.get_or_create(
            product=item.product,
            warehouse=instance.warehouse,
            defaults={'quantity': 0},
        )
        stock.quantity += item.quantity
        stock.save()
        StockMovement.objects.create(
            product=item.product,
            warehouse=instance.warehouse,
            movement_type='in',
            quantity=item.quantity,
            reference_type='PO',
            reference_number=instance.po_number,
            notes=f'PO {instance.po_number} received',
        )


@receiver(pre_save, sender=SalesOrder)
def so_shipped_update_stock(sender, instance, **kwargs):
    """When a SO first moves to 'shipped' or 'delivered', deduct items from stock."""
    if not instance.pk:
        return
    try:
        old = SalesOrder.objects.get(pk=instance.pk)
    except SalesOrder.DoesNotExist:
        return
    outgoing = ('shipped', 'delivered')
    if old.status in outgoing or instance.status not in outgoing:
        return
    for item in instance.items.select_related('product').all():
        stock = Stock.objects.filter(
            product=item.product,
            warehouse=instance.warehouse,
        ).first()
        if not stock:
            continue
        deduct = min(item.quantity, stock.quantity)
        stock.quantity -= deduct
        stock.save()
        StockMovement.objects.create(
            product=item.product,
            warehouse=instance.warehouse,
            movement_type='out',
            quantity=-deduct,
            reference_type='SO',
            reference_number=instance.so_number,
            notes=f'SO {instance.so_number} → {instance.status}',
        )
