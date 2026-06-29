from django.shortcuts import render
from inventory.models import Product, Stock
from suppliers.models import Supplier
from orders.models import PurchaseOrder, SalesOrder
from shipments.models import Shipment
from django.db.models import Sum, Count
import json


def dashboard(request):
    total_products = Product.objects.count()
    total_suppliers = Supplier.objects.filter(status='active').count()
    pending_po = PurchaseOrder.objects.filter(status__in=['draft', 'sent', 'confirmed']).count()
    pending_so = SalesOrder.objects.filter(status__in=['pending', 'processing']).count()
    in_transit = Shipment.objects.filter(status__in=['in_transit', 'out_for_delivery']).count()
    low_stock_products = [p for p in Product.objects.prefetch_related('stock_set') if p.is_low_stock]

    recent_po = PurchaseOrder.objects.select_related('supplier').order_by('-created_at')[:5]
    recent_so = SalesOrder.objects.order_by('-created_at')[:5]
    recent_shipments = Shipment.objects.order_by('-created_at')[:5]

    so_status_data = list(
        SalesOrder.objects.values('status').annotate(count=Count('id'))
    )
    so_labels = [d['status'].title() for d in so_status_data]
    so_counts = [d['count'] for d in so_status_data]

    return render(request, 'dashboard/dashboard.html', {
        'total_products': total_products,
        'total_suppliers': total_suppliers,
        'pending_po': pending_po,
        'pending_so': pending_so,
        'in_transit': in_transit,
        'low_stock_products': low_stock_products,
        'recent_po': recent_po,
        'recent_so': recent_so,
        'recent_shipments': recent_shipments,
        'so_labels': json.dumps(so_labels),
        'so_counts': json.dumps(so_counts),
    })
