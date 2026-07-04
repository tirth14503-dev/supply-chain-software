from django.shortcuts import render
from inventory.models import Product, Stock
from suppliers.models import Supplier
from orders.models import PurchaseOrder, SalesOrder, SalesOrderItem, PurchaseOrderItem
from shipments.models import Shipment
from django.db.models import Sum, Count
import json
import datetime
from collections import defaultdict


def _financial_summary():
    """Returns core financial KPIs used by both dashboard and finance report."""
    today = datetime.date.today()
    month_start = today.replace(day=1)

    products = list(Product.objects.prefetch_related('stock_set').all())
    inv_value = sum(p.stock_value for p in products)

    mtd_items = list(SalesOrderItem.objects.filter(
        order__status__in=['shipped', 'delivered'],
        order__created_at__date__gte=month_start,
    ).select_related('product', 'order'))

    revenue_mtd = sum(float(i.quantity) * float(i.unit_price) for i in mtd_items)
    cogs_mtd = sum(float(i.quantity) * float(i.product.unit_price) for i in mtd_items)
    gross_profit = revenue_mtd - cogs_mtd
    gross_margin = (gross_profit / revenue_mtd * 100) if revenue_mtd else 0

    open_pos = list(PurchaseOrder.objects.filter(
        status__in=['draft', 'sent', 'confirmed']
    ).prefetch_related('items'))
    ap_total = sum(float(po.total_amount) for po in open_pos)

    open_sos = list(SalesOrder.objects.filter(
        status__in=['pending', 'processing', 'shipped']
    ).prefetch_related('items'))
    ar_total = sum(float(so.total_amount) for so in open_sos)

    return {
        'inv_value': round(inv_value, 2),
        'revenue_mtd': round(revenue_mtd, 2),
        'cogs_mtd': round(cogs_mtd, 2),
        'gross_profit': round(gross_profit, 2),
        'gross_margin': round(gross_margin, 1),
        'ap_total': round(ap_total, 2),
        'ar_total': round(ar_total, 2),
    }


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

    fin = _financial_summary()

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
        **fin,
    })


def finance_report(request):
    today = datetime.date.today()
    fin = _financial_summary()

    # Monthly revenue & COGS for last 6 months
    monthly_labels, monthly_revenue, monthly_cogs, monthly_profit = [], [], [], []
    for i in range(5, -1, -1):
        first_of = (today.replace(day=1) - datetime.timedelta(days=30 * i))
        start = first_of.replace(day=1)
        if i == 0:
            end = today
        else:
            nxt = start.replace(day=28) + datetime.timedelta(days=4)
            end = nxt.replace(day=1) - datetime.timedelta(days=1)

        items = list(SalesOrderItem.objects.filter(
            order__status__in=['shipped', 'delivered'],
            order__created_at__date__gte=start,
            order__created_at__date__lte=end,
        ).select_related('product'))

        rev = sum(float(i.quantity) * float(i.unit_price) for i in items)
        cogs = sum(float(i.quantity) * float(i.product.unit_price) for i in items)
        monthly_labels.append(start.strftime('%b %Y'))
        monthly_revenue.append(round(rev, 2))
        monthly_cogs.append(round(cogs, 2))
        monthly_profit.append(round(rev - cogs, 2))

    # Top 5 products by total revenue (all time)
    prod_rev = defaultdict(float)
    prod_margin = defaultdict(float)
    for item in SalesOrderItem.objects.filter(
        order__status__in=['shipped', 'delivered']
    ).select_related('product'):
        rev = float(item.quantity) * float(item.unit_price)
        cogs = float(item.quantity) * float(item.product.unit_price)
        prod_rev[item.product.name] += rev
        prod_margin[item.product.name] += (rev - cogs)
    top_products = sorted(
        [{'name': k, 'revenue': round(v, 2),
          'margin': round(prod_margin[k] / v * 100, 1) if v else 0}
         for k, v in prod_rev.items()],
        key=lambda x: -x['revenue']
    )[:8]

    # Inventory value by category
    cat_values = defaultdict(float)
    for p in Product.objects.prefetch_related('stock_set').select_related('category'):
        cat_name = p.category.name if p.category else 'Uncategorized'
        cat_values[cat_name] += p.stock_value
    cat_values = sorted(
        [{'name': k, 'value': round(v, 2)} for k, v in cat_values.items()],
        key=lambda x: -x['value']
    )

    # Open AP details
    open_pos = PurchaseOrder.objects.filter(
        status__in=['draft', 'sent', 'confirmed']
    ).select_related('supplier').prefetch_related('items').order_by('-created_at')

    # Open AR details
    open_sos = SalesOrder.objects.filter(
        status__in=['pending', 'processing', 'shipped']
    ).prefetch_related('items').order_by('-created_at')

    return render(request, 'dashboard/finance_report.html', {
        **fin,
        'monthly_labels': json.dumps(monthly_labels),
        'monthly_revenue': json.dumps(monthly_revenue),
        'monthly_cogs': json.dumps(monthly_cogs),
        'monthly_profit': json.dumps(monthly_profit),
        'top_products': top_products,
        'cat_values': cat_values,
        'open_pos': open_pos,
        'open_sos': open_sos,
    })
