import math
from datetime import timedelta
from pathlib import Path

import joblib
import pandas as pd
from django.db.models import Sum
from django.utils import timezone

from orders.models import PurchaseOrder, SalesOrderItem

from . import features

ARTIFACT_DIR = Path(__file__).resolve().parent / 'artifacts'
_cache = {}


def _load(name):
    """Lazily load + cache a trained pipeline; returns None if it hasn't been trained yet."""
    if name not in _cache:
        path = ARTIFACT_DIR / f'{name}.joblib'
        _cache[name] = joblib.load(path) if path.exists() else None
    return _cache[name]


def _recent_monthly(product, n=3):
    today = timezone.now().date()
    vals = []
    for i in range(n - 1, -1, -1):
        start = today - timedelta(days=30 * (i + 1))
        end = today - timedelta(days=30 * i)
        qty = SalesOrderItem.objects.filter(
            product=product, order__created_at__date__gte=start, order__created_at__date__lt=end,
        ).aggregate(t=Sum('quantity'))['t'] or 0
        vals.append(qty)
    return vals, today


def predict_demand(product):
    """Next-month forecasted quantity for a product, or None if the model isn't trained."""
    model = _load('demand_forecast')
    if model is None:
        return None
    try:
        lags, today = _recent_monthly(product, 3)
        next_month = today + timedelta(days=30)
        angle = 2 * math.pi * next_month.month / 12
        rolling_mean = sum(lags) / 3
        row = pd.DataFrame([{
            'category': product.category.name if product.category else 'Unknown',
            'unit_price': float(product.unit_price),
            'reorder_point': product.reorder_point,
            'month_sin': math.sin(angle),
            'month_cos': math.cos(angle),
            'lag1': lags[-1], 'lag2': lags[-2], 'lag3': lags[-3],
            'rolling_mean_3': rolling_mean,
        }])
        ratio = model.predict(row)[0]
        return max(0, round(ratio * max(rolling_mean, 1)))
    except Exception:
        return None


def predict_supplier_risk(supplier):
    """Probability (0-1) that this supplier's purchase orders run into trouble (cancelled/late)."""
    model = _load('supplier_risk')
    if model is None:
        return None
    try:
        pos = PurchaseOrder.objects.filter(supplier=supplier).exclude(status='draft').prefetch_related('items')
        rows = [{
            'supplier_rating': float(supplier.rating), 'supplier_lead_time': supplier.lead_time_days,
            'supplier_status': supplier.status, 'order_quantity': sum(i.quantity for i in po.items.all()),
            'order_value': float(po.total_amount),
            'order_month': po.order_date.month if po.order_date else timezone.now().date().month,
        } for po in pos]
        if not rows:
            rows = [{
                'supplier_rating': float(supplier.rating), 'supplier_lead_time': supplier.lead_time_days,
                'supplier_status': supplier.status, 'order_quantity': 0, 'order_value': 0.0,
                'order_month': timezone.now().date().month,
            }]
        df = pd.DataFrame(rows)
        return float(model.predict_proba(df)[:, 1].mean())
    except Exception:
        return None


def predict_delay_probability(shipment):
    """Probability (0-1) that an in-flight shipment will arrive later than its estimate."""
    model = _load('delay_predictor')
    if model is None or not shipment.ship_date or not shipment.estimated_delivery:
        return None
    try:
        supplier = None
        if shipment.shipment_type == 'inbound' and shipment.purchase_order:
            supplier = shipment.purchase_order.supplier
        row = pd.DataFrame([{
            'carrier': shipment.carrier, 'shipment_type': shipment.shipment_type,
            'weight_kg': float(shipment.weight_kg) if shipment.weight_kg else 0.0,
            'planned_transit_days': (shipment.estimated_delivery - shipment.ship_date).days,
            'supplier_rating': float(supplier.rating) if supplier else 4.0,
            'supplier_lead_time': supplier.lead_time_days if supplier else 7,
            'ship_month': shipment.ship_date.month,
        }])
        return float(model.predict_proba(row)[:, 1][0])
    except Exception:
        return None


def score_anomaly(product_id, quantity):
    """(is_anomaly, decision_score, z_score) for a single order quantity, or None if untrained."""
    model = _load('anomaly_detector')
    if model is None:
        return None
    try:
        mean, std = features.product_quantity_stats(product_id)
        ratio = quantity / max(mean, 1e-6)
        z = (quantity - mean) / std
        row = pd.DataFrame([{'qty_ratio': ratio, 'qty_zscore': z}])
        is_anomaly = bool(model.predict(row)[0] == -1)
        score = float(model.decision_function(row)[0])
        return is_anomaly, score, z
    except Exception:
        return None


def models_available():
    return {
        name: (ARTIFACT_DIR / f'{name}.joblib').exists()
        for name in ('demand_forecast', 'supplier_risk', 'delay_predictor', 'anomaly_detector')
    }
