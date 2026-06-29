from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Q
from .models import PurchaseOrder, PurchaseOrderItem, SalesOrder, SalesOrderItem
from inventory.models import Product, Warehouse
from suppliers.models import Supplier
import uuid


def _gen_po():
    return f'PO-{uuid.uuid4().hex[:8].upper()}'


def _gen_so():
    return f'SO-{uuid.uuid4().hex[:8].upper()}'


# ── Purchase Orders ──────────────────────────────────────────────────────────

def po_list(request):
    q = request.GET.get('q', '')
    status = request.GET.get('status', '')
    orders = PurchaseOrder.objects.select_related('supplier', 'warehouse').order_by('-created_at')
    if q:
        orders = orders.filter(Q(po_number__icontains=q) | Q(supplier__name__icontains=q))
    if status:
        orders = orders.filter(status=status)
    return render(request, 'orders/po_list.html', {'orders': orders, 'q': q, 'status': status})


def po_detail(request, pk):
    order = get_object_or_404(PurchaseOrder, pk=pk)
    items = order.items.select_related('product')
    return render(request, 'orders/po_detail.html', {'order': order, 'items': items})


def po_create(request):
    if request.method == 'POST':
        order = PurchaseOrder.objects.create(
            po_number=_gen_po(),
            supplier_id=request.POST['supplier'],
            warehouse_id=request.POST['warehouse'],
            expected_date=request.POST.get('expected_date') or None,
            notes=request.POST.get('notes', '')
        )
        product_ids = request.POST.getlist('product_id')
        quantities = request.POST.getlist('quantity')
        prices = request.POST.getlist('unit_price')
        for pid, qty, price in zip(product_ids, quantities, prices):
            if pid and qty:
                PurchaseOrderItem.objects.create(
                    order=order, product_id=pid, quantity=qty, unit_price=price
                )
        messages.success(request, f'Purchase Order {order.po_number} created.')
        return redirect('po_detail', pk=order.pk)
    suppliers = Supplier.objects.filter(status='active')
    warehouses = Warehouse.objects.all()
    products = Product.objects.all()
    return render(request, 'orders/po_form.html', {
        'suppliers': suppliers, 'warehouses': warehouses, 'products': products, 'action': 'Create'
    })


def po_update_status(request, pk):
    order = get_object_or_404(PurchaseOrder, pk=pk)
    if request.method == 'POST':
        order.status = request.POST['status']
        order.save()
        if order.status == 'received':
            for item in order.items.all():
                from inventory.models import Stock
                stock, _ = Stock.objects.get_or_create(product=item.product, warehouse=order.warehouse)
                stock.quantity += item.quantity
                stock.save()
            messages.success(request, 'Order marked received — stock updated.')
        else:
            messages.success(request, 'Status updated.')
    return redirect('po_detail', pk=pk)


# ── Sales Orders ──────────────────────────────────────────────────────────────

def so_list(request):
    q = request.GET.get('q', '')
    status = request.GET.get('status', '')
    orders = SalesOrder.objects.select_related('warehouse').order_by('-created_at')
    if q:
        orders = orders.filter(Q(so_number__icontains=q) | Q(customer_name__icontains=q))
    if status:
        orders = orders.filter(status=status)
    return render(request, 'orders/so_list.html', {'orders': orders, 'q': q, 'status': status})


def so_detail(request, pk):
    order = get_object_or_404(SalesOrder, pk=pk)
    items = order.items.select_related('product')
    return render(request, 'orders/so_detail.html', {'order': order, 'items': items})


def so_create(request):
    if request.method == 'POST':
        order = SalesOrder.objects.create(
            so_number=_gen_so(),
            customer_name=request.POST['customer_name'],
            customer_email=request.POST.get('customer_email', ''),
            customer_phone=request.POST.get('customer_phone', ''),
            shipping_address=request.POST.get('shipping_address', ''),
            warehouse_id=request.POST['warehouse'],
            required_date=request.POST.get('required_date') or None,
            notes=request.POST.get('notes', '')
        )
        product_ids = request.POST.getlist('product_id')
        quantities = request.POST.getlist('quantity')
        prices = request.POST.getlist('unit_price')
        for pid, qty, price in zip(product_ids, quantities, prices):
            if pid and qty:
                SalesOrderItem.objects.create(
                    order=order, product_id=pid, quantity=qty, unit_price=price
                )
        messages.success(request, f'Sales Order {order.so_number} created.')
        return redirect('so_detail', pk=order.pk)
    warehouses = Warehouse.objects.all()
    products = Product.objects.all()
    return render(request, 'orders/so_form.html', {
        'warehouses': warehouses, 'products': products, 'action': 'Create'
    })


def so_update_status(request, pk):
    order = get_object_or_404(SalesOrder, pk=pk)
    if request.method == 'POST':
        order.status = request.POST['status']
        order.save()
        messages.success(request, 'Status updated.')
    return redirect('so_detail', pk=pk)
