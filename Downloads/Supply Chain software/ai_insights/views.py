from django.shortcuts import render
from django.utils import timezone
from django.db.models import Sum
from inventory.models import Product
from suppliers.models import Supplier
from orders.models import PurchaseOrder, SalesOrderItem
from shipments.models import Shipment
from datetime import timedelta
import json


# ── helpers ───────────────────────────────────────────────────────────────────

def _reorder_alerts():
    alerts = []
    for product in Product.objects.prefetch_related('stock_set').all():
        stock = product.total_stock
        cutoff = timezone.now() - timedelta(days=30)
        sold = SalesOrderItem.objects.filter(
            product=product,
            order__created_at__gte=cutoff,
            order__status__in=['processing', 'shipped', 'delivered'],
        ).aggregate(t=Sum('quantity'))['t'] or 0
        avg_daily = sold / 30 if sold else 0.5
        days_out = int(stock / avg_daily) if avg_daily else 999
        if stock <= product.reorder_point or days_out <= 14:
            rec_qty = max(int(avg_daily * 30), product.reorder_point * 2, 10)
            urgency = ('Critical' if days_out <= 3 or stock == 0
                       else 'High' if days_out <= 7 else 'Medium')
            alerts.append({
                'product': product, 'current_stock': stock,
                'reorder_point': product.reorder_point,
                'days_until_stockout': min(days_out, 999),
                'recommended_qty': rec_qty, 'urgency': urgency,
                'avg_daily_sales': round(avg_daily, 2),
            })
    order = {'Critical': 0, 'High': 1, 'Medium': 2}
    return sorted(alerts, key=lambda x: order.get(x['urgency'], 3))


def _supplier_risks():
    risks = []
    for s in Supplier.objects.all():
        score, factors = 100, []
        if s.status == 'blacklisted':
            score -= 50; factors.append('Blacklisted supplier')
        elif s.status == 'inactive':
            score -= 20; factors.append('Inactive supplier')
        if s.rating < 3:
            score -= 25; factors.append(f'Low rating ({s.rating}/5)')
        elif s.rating < 4:
            score -= 10; factors.append(f'Below-avg rating ({s.rating}/5)')
        if s.lead_time_days > 21:
            score -= 20; factors.append(f'Very long lead time ({s.lead_time_days}d)')
        elif s.lead_time_days > 14:
            score -= 10; factors.append(f'Long lead time ({s.lead_time_days}d)')
        total = PurchaseOrder.objects.filter(supplier=s).count()
        cancelled = PurchaseOrder.objects.filter(supplier=s, status='cancelled').count()
        if total:
            rate = cancelled / total * 100
            if rate > 30:
                score -= 20; factors.append(f'High cancellation rate ({rate:.0f}%)')
            elif rate > 10:
                score -= 10; factors.append(f'Elevated cancellation rate ({rate:.0f}%)')
        score = max(0, score)
        level = 'Low' if score >= 75 else 'Medium' if score >= 50 else 'High'
        risks.append({'supplier': s, 'score': score, 'risk_level': level,
                      'risk_factors': factors, 'total_pos': total})
    return sorted(risks, key=lambda x: x['score'])


def _anomalies():
    anomalies = []
    for product in Product.objects.all():
        qtys = list(SalesOrderItem.objects.filter(product=product)
                    .values_list('quantity', flat=True))
        if len(qtys) < 2:
            continue
        mean = sum(qtys) / len(qtys)
        # Bessel's correction: divide by N-1 for unbiased sample std dev
        std = (sum((q - mean) ** 2 for q in qtys) / (len(qtys) - 1)) ** 0.5
        if std == 0:
            continue
        for item in SalesOrderItem.objects.filter(product=product).select_related('order').order_by('-id')[:10]:
            z = abs(item.quantity - mean) / std
            if z > 2:
                anomalies.append({
                    'type': 'Unusual Order Quantity', 'product': product,
                    'order': item.order, 'quantity': item.quantity,
                    'normal_range': f'{max(0,int(mean-2*std))}–{int(mean+2*std)}',
                    'severity': 'High' if z > 3 else 'Medium',
                    'z_score': round(z, 2),
                })
    return anomalies


def _delay_risks():
    today = timezone.now().date()
    risks = []
    for s in Shipment.objects.filter(status__in=['pending', 'in_transit']):
        if not s.estimated_delivery:
            continue
        if s.estimated_delivery < today:
            risks.append({'shipment': s,
                          'days_overdue': (today - s.estimated_delivery).days,
                          'days_remaining': None,
                          'severity': 'High' if (today - s.estimated_delivery).days > 3 else 'Medium'})
        elif (s.estimated_delivery - today).days <= 3:
            risks.append({'shipment': s, 'days_overdue': 0,
                          'days_remaining': (s.estimated_delivery - today).days,
                          'severity': 'Medium'})
    return risks


# ── views ─────────────────────────────────────────────────────────────────────

def ai_dashboard(request):
    reorder = _reorder_alerts()
    risks = _supplier_risks()
    anomalies = _anomalies()
    delays = _delay_risks()
    high_risk = [r for r in risks if r['risk_level'] == 'High']
    return render(request, 'ai_insights/dashboard.html', {
        'reorder_count': len(reorder),
        'high_risk_count': len(high_risk),
        'anomaly_count': len(anomalies),
        'delay_count': len(delays),
        'reorder_alerts': reorder[:3],
        'supplier_risks': risks[:3],
        'anomalies': anomalies[:3],
        'delay_risks': delays[:3],
    })


def demand_forecast(request):
    forecasts = []
    for product in Product.objects.prefetch_related('stock_set').all():
        monthly = []
        for i in range(5, -1, -1):
            start = (timezone.now() - timedelta(days=30 * (i + 1))).date()
            end = (timezone.now() - timedelta(days=30 * i)).date()
            sold = SalesOrderItem.objects.filter(
                product=product,
                order__created_at__date__gte=start,
                order__created_at__date__lt=end,
                order__status__in=['processing', 'shipped', 'delivered'],
            ).aggregate(t=Sum('quantity'))['t'] or 0
            monthly.append(sold)
        avg = sum(monthly) / 6 if sum(monthly) else product.reorder_point * 0.5
        first3 = sum(monthly[:3]) / 3
        last3 = sum(monthly[3:]) / 3
        # Use 0.1 as floor so fractional demand (e.g. 0.5/mo) isn't distorted
        trend = ((last3 - first3) / max(first3, 0.1)) * 100 if sum(monthly) else 0
        forecast_qty = max(0, int(avg * (1 + trend / 100)))
        stock = product.total_stock
        forecasts.append({
            'product': product,
            'current_stock': stock,
            'monthly_data': monthly,
            'avg_monthly': round(avg, 1),
            'trend_pct': round(trend, 1),
            'forecast_next_month': forecast_qty,
            'stock_coverage_months': round(stock / max(avg, 0.1), 1),
        })
    return render(request, 'ai_insights/demand_forecast.html', {
        'forecasts': forecasts,
        'chart_labels': json.dumps([f['product'].name[:15] for f in forecasts]),
        'chart_forecast': json.dumps([f['forecast_next_month'] for f in forecasts]),
        'chart_stock': json.dumps([f['current_stock'] for f in forecasts]),
    })


def smart_reorder(request):
    return render(request, 'ai_insights/smart_reorder.html',
                  {'alerts': _reorder_alerts()})


def supplier_risk(request):
    risks = _supplier_risks()
    counts = {'Low': 0, 'Medium': 0, 'High': 0}
    for r in risks:
        counts[r['risk_level']] += 1
    return render(request, 'ai_insights/supplier_risk.html', {
        'risks': risks,
        'risk_counts': counts,
        'chart_data': json.dumps([counts['Low'], counts['Medium'], counts['High']]),
    })


def anomaly_detection(request):
    return render(request, 'ai_insights/anomaly_detection.html',
                  {'anomalies': _anomalies()})


def delay_predictor(request):
    today = timezone.now().date()
    upcoming = Shipment.objects.filter(
        status__in=['pending', 'in_transit'],
        estimated_delivery__gte=today,
    ).order_by('estimated_delivery')
    return render(request, 'ai_insights/delay_predictor.html', {
        'risks': _delay_risks(),
        'upcoming': upcoming,
    })
