from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Q
from .models import Supplier


def supplier_list(request):
    q = request.GET.get('q', '')
    status = request.GET.get('status', '')
    suppliers = Supplier.objects.all()
    if q:
        suppliers = suppliers.filter(Q(name__icontains=q) | Q(email__icontains=q) | Q(country__icontains=q))
    if status:
        suppliers = suppliers.filter(status=status)
    return render(request, 'suppliers/supplier_list.html', {'suppliers': suppliers, 'q': q, 'status': status})


def supplier_detail(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    purchase_orders = supplier.purchaseorder_set.order_by('-created_at')[:10]
    return render(request, 'suppliers/supplier_detail.html', {
        'supplier': supplier, 'purchase_orders': purchase_orders
    })


def supplier_create(request):
    if request.method == 'POST':
        s = Supplier.objects.create(
            name=request.POST['name'],
            contact_person=request.POST.get('contact_person', ''),
            email=request.POST.get('email', ''),
            phone=request.POST.get('phone', ''),
            address=request.POST.get('address', ''),
            country=request.POST.get('country', ''),
            status=request.POST.get('status', 'active'),
            payment_terms=request.POST.get('payment_terms', ''),
            lead_time_days=request.POST.get('lead_time_days', 7),
            rating=request.POST.get('rating', 5.0),
            notes=request.POST.get('notes', '')
        )
        messages.success(request, f'Supplier "{s.name}" created.')
        return redirect('supplier_list')
    return render(request, 'suppliers/supplier_form.html', {'action': 'Create'})


def supplier_edit(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    if request.method == 'POST':
        supplier.name = request.POST['name']
        supplier.contact_person = request.POST.get('contact_person', '')
        supplier.email = request.POST.get('email', '')
        supplier.phone = request.POST.get('phone', '')
        supplier.address = request.POST.get('address', '')
        supplier.country = request.POST.get('country', '')
        supplier.status = request.POST.get('status', 'active')
        supplier.payment_terms = request.POST.get('payment_terms', '')
        supplier.lead_time_days = request.POST.get('lead_time_days', 7)
        supplier.rating = request.POST.get('rating', 5.0)
        supplier.notes = request.POST.get('notes', '')
        supplier.save()
        messages.success(request, 'Supplier updated.')
        return redirect('supplier_detail', pk=pk)
    return render(request, 'suppliers/supplier_form.html', {'supplier': supplier, 'action': 'Edit'})


def supplier_delete(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    if request.method == 'POST':
        supplier.delete()
        messages.success(request, 'Supplier deleted.')
        return redirect('supplier_list')
    return render(request, 'suppliers/confirm_delete.html', {'object': supplier, 'type': 'Supplier'})
