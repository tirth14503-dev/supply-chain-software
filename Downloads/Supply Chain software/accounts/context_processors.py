from django.utils import timezone
from inventory.models import Product
from shipments.models import Shipment


def user_roles(request):
    if not request.user.is_authenticated:
        return {}

    su = request.user.is_superuser
    groups = set(request.user.groups.values_list('name', flat=True))

    def can(*roles):
        return su or bool(groups & (set(roles) | {'Admin'}))

    # Lightweight notification counts
    try:
        low_stock_count = sum(
            1 for p in Product.objects.prefetch_related('stock_set').all()
            if p.is_low_stock
        )
        today = timezone.now().date()
        overdue_count = Shipment.objects.filter(
            status__in=['pending', 'in_transit'],
            estimated_delivery__lt=today,
        ).count()
    except Exception:
        low_stock_count = 0
        overdue_count = 0

    return {
        'user_is_admin':   su or 'Admin' in groups,
        'user_is_manager': can('Manager'),
        'can_inventory':   can('Manager', 'Warehouse'),
        'can_procurement': can('Manager', 'Procurement'),
        'can_sales':       can('Manager', 'Sales'),
        'can_logistics':   can('Manager', 'Procurement', 'Sales'),
        'can_finance':     can('Manager'),
        'can_ai':          can('Manager'),
        'user_groups':     groups,
        'notif_low_stock': low_stock_count,
        'notif_overdue':   overdue_count,
    }
