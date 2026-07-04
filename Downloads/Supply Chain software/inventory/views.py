from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse
from .models import Product, Category, Warehouse, Stock, StockMovement


def product_list(request):
    q = request.GET.get('q', '')
    category_id = request.GET.get('category', '')
    products = Product.objects.select_related('category').prefetch_related('stock_set')
    if q:
        products = products.filter(Q(name__icontains=q) | Q(sku__icontains=q))
    if category_id:
        products = products.filter(category_id=category_id)
    categories = Category.objects.all()
    return render(request, 'inventory/product_list.html', {
        'products': products, 'categories': categories, 'q': q, 'category_id': category_id
    })


def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    stocks = Stock.objects.filter(product=product).select_related('warehouse')
    return render(request, 'inventory/product_detail.html', {'product': product, 'stocks': stocks})


def product_create(request):
    if request.method == 'POST':
        product = Product.objects.create(
            sku=request.POST['sku'],
            name=request.POST['name'],
            category_id=request.POST.get('category') or None,
            description=request.POST.get('description', ''),
            unit_price=request.POST['unit_price'],
            unit=request.POST.get('unit', 'pcs'),
            reorder_point=request.POST.get('reorder_point', 10),
            barcode=request.POST.get('barcode', ''),
        )
        messages.success(request, f'Product "{product.name}" created.')
        return redirect('product_list')
    categories = Category.objects.all()
    return render(request, 'inventory/product_form.html', {'categories': categories, 'action': 'Create'})


def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        product.sku = request.POST['sku']
        product.name = request.POST['name']
        product.category_id = request.POST.get('category') or None
        product.description = request.POST.get('description', '')
        product.unit_price = request.POST['unit_price']
        product.unit = request.POST.get('unit', 'pcs')
        product.reorder_point = request.POST.get('reorder_point', 10)
        product.barcode = request.POST.get('barcode', '')
        product.save()
        messages.success(request, f'Product "{product.name}" updated.')
        return redirect('product_detail', pk=pk)
    categories = Category.objects.all()
    return render(request, 'inventory/product_form.html', {
        'product': product, 'categories': categories, 'action': 'Edit'
    })


def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        product.delete()
        messages.success(request, 'Product deleted.')
        return redirect('product_list')
    return render(request, 'inventory/confirm_delete.html', {'object': product, 'type': 'Product'})


def warehouse_list(request):
    warehouses = Warehouse.objects.all()
    return render(request, 'inventory/warehouse_list.html', {'warehouses': warehouses})


def warehouse_create(request):
    if request.method == 'POST':
        w = Warehouse.objects.create(
            name=request.POST['name'],
            location=request.POST['location'],
            capacity=request.POST.get('capacity', 0),
            manager=request.POST.get('manager', '')
        )
        messages.success(request, f'Warehouse "{w.name}" created.')
        return redirect('warehouse_list')
    return render(request, 'inventory/warehouse_form.html', {'action': 'Create'})


def warehouse_edit(request, pk):
    warehouse = get_object_or_404(Warehouse, pk=pk)
    if request.method == 'POST':
        warehouse.name = request.POST['name']
        warehouse.location = request.POST['location']
        warehouse.capacity = request.POST.get('capacity', 0)
        warehouse.manager = request.POST.get('manager', '')
        warehouse.save()
        messages.success(request, 'Warehouse updated.')
        return redirect('warehouse_list')
    return render(request, 'inventory/warehouse_form.html', {'warehouse': warehouse, 'action': 'Edit'})


def stock_adjust(request, product_pk):
    product = get_object_or_404(Product, pk=product_pk)
    warehouses = Warehouse.objects.all()
    if request.method == 'POST':
        warehouse_id = request.POST['warehouse']
        new_qty = int(request.POST['quantity'])
        notes = request.POST.get('notes', '')
        stock, _ = Stock.objects.get_or_create(product=product, warehouse_id=warehouse_id, defaults={'quantity': 0})
        diff = new_qty - stock.quantity
        stock.quantity = new_qty
        stock.save()
        if diff != 0:
            StockMovement.objects.create(
                product=product,
                warehouse_id=warehouse_id,
                movement_type='adjustment',
                quantity=diff,
                reference_type='Manual',
                reference_number='',
                notes=notes or f'Manual adjustment → {new_qty}',
                created_by=str(request.user),
            )
        messages.success(request, 'Stock updated and movement logged.')
        return redirect('product_detail', pk=product_pk)
    return render(request, 'inventory/stock_adjust.html', {'product': product, 'warehouses': warehouses})


def stock_ledger(request):
    qs = StockMovement.objects.select_related('product', 'warehouse').all()
    product_id = request.GET.get('product')
    warehouse_id = request.GET.get('warehouse')
    if product_id:
        qs = qs.filter(product_id=product_id)
    if warehouse_id:
        qs = qs.filter(warehouse_id=warehouse_id)
    movements = qs[:200]
    products = Product.objects.all()
    warehouses = Warehouse.objects.all()
    return render(request, 'inventory/stock_ledger.html', {
        'movements': movements,
        'products': products,
        'warehouses': warehouses,
        'selected_product': product_id,
        'selected_warehouse': warehouse_id,
    })


def barcode_scan(request):
    return render(request, 'inventory/barcode_scan.html')


def product_lookup(request):
    code = request.GET.get('code', '').strip()
    if not code:
        return JsonResponse({'found': False, 'error': 'No code provided'})

    product = (
        Product.objects.filter(barcode=code).first()
        or Product.objects.filter(sku__iexact=code).first()
        or Product.objects.filter(name__iexact=code).first()
    )

    if not product:
        return JsonResponse({'found': False, 'code': code})

    stocks = list(Stock.objects.filter(product=product).select_related('warehouse'))
    return JsonResponse({
        'found': True,
        'id': product.pk,
        'sku': product.sku,
        'name': product.name,
        'barcode': product.barcode or product.sku,
        'category': product.category.name if product.category else '',
        'unit_price': float(product.unit_price),
        'unit': product.unit,
        'total_stock': product.total_stock,
        'is_low_stock': product.is_low_stock,
        'reorder_point': product.reorder_point,
        'stock_value': product.stock_value,
        'detail_url': f'/inventory/products/{product.pk}/',
        'adjust_url': f'/inventory/products/{product.pk}/stock/',
        'print_url': f'/inventory/products/{product.pk}/barcode/',
        'stocks': [
            {'warehouse': s.warehouse.name, 'location': s.warehouse.location, 'quantity': s.quantity}
            for s in stocks
        ],
    })


def barcode_print(request, pk):
    product = get_object_or_404(Product, pk=pk)
    barcode_value = product.barcode or product.sku
    copies = int(request.GET.get('copies', 1))
    return render(request, 'inventory/barcode_print.html', {
        'product': product,
        'barcode_value': barcode_value,
        'copies': range(copies),
        'copies_count': copies,
    })
