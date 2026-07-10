import math
from datetime import timedelta

import pandas as pd
from django.db.models import Sum
from django.utils import timezone

from inventory.models import Product
from orders.models import PurchaseOrder, SalesOrderItem
from shipments.models import Shipment

LAG_WINDOW = 3


def _monthly_sales_matrix(months):
    """(product, [oldest ... newest monthly quantity]) for every product."""
    today = timezone.now().date()
    rows = []
    for product in Product.objects.select_related('category').all():
        monthly = []
        for i in range(months - 1, -1, -1):
            start = today - timedelta(days=30 * (i + 1))
            end = today - timedelta(days=30 * i)
            qty = SalesOrderItem.objects.filter(
                product=product,
                order__created_at__date__gte=start,
                order__created_at__date__lt=end,
            ).aggregate(t=Sum('quantity'))['t'] or 0
            monthly.append(qty)
        rows.append((product, monthly, today))
    return rows


def build_demand_dataset(months=15):
    """One row per (product, month) with lag features; target = that month's actual quantity."""
    records = []
    for product, monthly, today in _monthly_sales_matrix(months):
        for t in range(LAG_WINDOW, len(monthly)):
            bucket_date = today - timedelta(days=30 * (len(monthly) - t))
            month_angle = 2 * math.pi * bucket_date.month / 12
            lags = monthly[t - LAG_WINDOW:t]
            records.append({
                'category': product.category.name if product.category else 'Unknown',
                'unit_price': float(product.unit_price),
                'reorder_point': product.reorder_point,
                'month_sin': math.sin(month_angle),
                'month_cos': math.cos(month_angle),
                'lag1': lags[-1],
                'lag2': lags[-2],
                'lag3': lags[-3],
                'rolling_mean_3': sum(lags) / len(lags),
                'target': monthly[t],
            })
    df = pd.DataFrame.from_records(records)
    return df.drop(columns=['target']), df['target']


def build_supplier_risk_dataset():
    """One row per resolved purchase order; target = 1 if cancelled or delivered late."""
    shipment_by_po = {
        s.purchase_order_id: s for s in Shipment.objects.filter(purchase_order__isnull=False)
    }
    records = []
    pos = PurchaseOrder.objects.select_related('supplier').prefetch_related('items').exclude(status='draft')
    for po in pos:
        shipment = shipment_by_po.get(po.id)
        late = bool(
            shipment and shipment.actual_delivery and shipment.estimated_delivery
            and shipment.actual_delivery > shipment.estimated_delivery
        )
        risky = 1 if (po.status == 'cancelled' or late) else 0
        qty = sum(item.quantity for item in po.items.all())
        records.append({
            'supplier_rating': float(po.supplier.rating),
            'supplier_lead_time': po.supplier.lead_time_days,
            'supplier_status': po.supplier.status,
            'order_quantity': qty,
            'order_value': float(po.total_amount),
            'order_month': po.order_date.month if po.order_date else 1,
            'target': risky,
        })
    df = pd.DataFrame.from_records(records)
    return df.drop(columns=['target']), df['target']


def build_delay_dataset():
    """One row per completed shipment; target = 1 if delivered later than estimated."""
    records = []
    qs = Shipment.objects.exclude(actual_delivery=None).select_related('purchase_order__supplier')
    for s in qs:
        if not s.ship_date or not s.estimated_delivery:
            continue
        supplier = s.purchase_order.supplier if (s.shipment_type == 'inbound' and s.purchase_order) else None
        records.append({
            'carrier': s.carrier,
            'shipment_type': s.shipment_type,
            'weight_kg': float(s.weight_kg) if s.weight_kg else 0.0,
            'planned_transit_days': (s.estimated_delivery - s.ship_date).days,
            'supplier_rating': float(supplier.rating) if supplier else 4.0,
            'supplier_lead_time': supplier.lead_time_days if supplier else 7,
            'ship_month': s.ship_date.month,
            'target': int(s.actual_delivery > s.estimated_delivery),
        })
    df = pd.DataFrame.from_records(records)
    return df.drop(columns=['target']), df['target']


def build_anomaly_dataset():
    """Normalized per-product quantity features for unsupervised outlier detection."""
    items = SalesOrderItem.objects.select_related('product').all()
    records = [
        {'product_id': i.product_id, 'quantity': i.quantity, 'unit_price': float(i.unit_price)}
        for i in items
    ]
    df = pd.DataFrame.from_records(records)
    stats = df.groupby('product_id')['quantity'].agg(p_mean='mean', p_std='std')
    df = df.join(stats, on='product_id')
    df['p_std'] = df['p_std'].fillna(0)
    floor = df['p_mean'] * 0.3 + 1e-6
    df['p_std'] = df['p_std'].where(df['p_std'] > 1e-6, floor)
    df['qty_ratio'] = df['quantity'] / df['p_mean'].clip(lower=1e-6)
    df['qty_zscore'] = (df['quantity'] - df['p_mean']) / df['p_std']
    return df[['qty_ratio', 'qty_zscore']]


def product_quantity_stats(product_id):
    """Live per-product mean/std used to featurize a single order at inference time."""
    qtys = list(SalesOrderItem.objects.filter(product_id=product_id).values_list('quantity', flat=True))
    if not qtys:
        return 0.0, 1.0
    mean = sum(qtys) / len(qtys)
    std = (sum((q - mean) ** 2 for q in qtys) / len(qtys)) ** 0.5
    if std <= 1e-6:
        std = mean * 0.3 + 1e-6
    return mean, std
