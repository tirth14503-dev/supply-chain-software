from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Q
from .models import Shipment
import uuid


def shipment_list(request):
    q = request.GET.get('q', '')
    status = request.GET.get('status', '')
    stype = request.GET.get('type', '')
    shipments = Shipment.objects.order_by('-created_at')
    if q:
        shipments = shipments.filter(Q(tracking_number__icontains=q) | Q(carrier__icontains=q))
    if status:
        shipments = shipments.filter(status=status)
    if stype:
        shipments = shipments.filter(shipment_type=stype)
    return render(request, 'shipments/shipment_list.html', {
        'shipments': shipments, 'q': q, 'status': status, 'stype': stype
    })


def shipment_detail(request, pk):
    shipment = get_object_or_404(Shipment, pk=pk)
    return render(request, 'shipments/shipment_detail.html', {'shipment': shipment})


def shipment_create(request):
    from orders.models import SalesOrder, PurchaseOrder
    if request.method == 'POST':
        so_id = request.POST.get('sales_order') or None
        po_id = request.POST.get('purchase_order') or None
        s = Shipment.objects.create(
            tracking_number=request.POST.get('tracking_number') or f'TRK-{uuid.uuid4().hex[:10].upper()}',
            shipment_type=request.POST['shipment_type'],
            sales_order_id=so_id,
            purchase_order_id=po_id,
            carrier=request.POST['carrier'],
            origin=request.POST['origin'],
            destination=request.POST['destination'],
            ship_date=request.POST.get('ship_date') or None,
            estimated_delivery=request.POST.get('estimated_delivery') or None,
            weight_kg=request.POST.get('weight_kg') or None,
            notes=request.POST.get('notes', '')
        )
        messages.success(request, f'Shipment {s.tracking_number} created.')
        return redirect('shipment_detail', pk=s.pk)
    sales_orders = SalesOrder.objects.filter(status__in=['processing', 'pending'])
    purchase_orders = PurchaseOrder.objects.filter(status__in=['confirmed', 'sent'])
    return render(request, 'shipments/shipment_form.html', {
        'sales_orders': sales_orders, 'purchase_orders': purchase_orders, 'action': 'Create'
    })


def shipment_update_status(request, pk):
    shipment = get_object_or_404(Shipment, pk=pk)
    if request.method == 'POST':
        shipment.status = request.POST['status']
        if shipment.status == 'delivered':
            from django.utils import timezone
            shipment.actual_delivery = timezone.now().date()
        shipment.save()
        messages.success(request, 'Shipment status updated.')
    return redirect('shipment_detail', pk=pk)
