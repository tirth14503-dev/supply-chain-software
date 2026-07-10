import math
import random
from datetime import datetime, timedelta
from decimal import Decimal

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from inventory.models import Category, Warehouse, Product, Stock
from suppliers.models import Supplier
from orders.models import PurchaseOrder, PurchaseOrderItem, SalesOrder, SalesOrderItem
from shipments.models import Shipment

# carrier -> baseline transit days + delay behaviour, used to generate realistic
# shipment timing so the delay-predictor model has real signal to learn from
CARRIERS = {
    'FedEx': {'base_transit': 3, 'delay_prob': 0.10, 'delay_range': (1, 4)},
    'UPS':   {'base_transit': 4, 'delay_prob': 0.15, 'delay_range': (1, 4)},
    'DHL':   {'base_transit': 5, 'delay_prob': 0.20, 'delay_range': (2, 5)},
    'USPS':  {'base_transit': 6, 'delay_prob': 0.30, 'delay_range': (2, 7)},
}

CUSTOMERS = [
    ('Acme Corporation', 'Chicago, IL'), ('Beta Industries', 'Houston, TX'),
    ('Gamma Tech', 'San Francisco, CA'), ('Delta Logistics', 'Atlanta, GA'),
    ('Nova Manufacturing', 'Detroit, MI'), ('Orion Retail Group', 'Dallas, TX'),
    ('Summit Electronics', 'Seattle, WA'), ('Pioneer Freight', 'Newark, NJ'),
    ('Vertex Solutions', 'Denver, CO'), ('Harbor Trading Co.', 'Miami, FL'),
]

# name, contact, email, phone, country, terms, lead_time, rating, status, cancel_prob, delay_prob
EXTRA_SUPPLIERS = [
    ('Reliable Parts Co.', 'Nina Osei', 'nina@reliableparts.com', '+1-617-555-0111', 'USA', 'Net 30', 5, 4.9, 'active', 0.02, 0.05),
    ('Budget Supply Chain', 'Raj Mehta', 'raj@budgetsupply.in', '+91-22-555-0222', 'India', 'Net 60', 28, 2.6, 'active', 0.35, 0.45),
    ('Nordic Components AB', 'Erik Lindqvist', 'erik@nordiccomp.se', '+46-8-555-0333', 'Sweden', 'Net 45', 12, 4.3, 'active', 0.08, 0.15),
    ('Pacific Rim Traders', 'Mei Lin', 'mei@pacrim.cn', '+86-21-555-0444', 'China', 'Net 30', 20, 3.4, 'active', 0.18, 0.30),
    ('Sunrise Industrial', 'Carlos Diaz', 'carlos@sunriseind.com', '+1-713-555-0555', 'USA', 'Net 30', 9, 4.0, 'inactive', 0.20, 0.25),
    ('Vantage Materials', 'Fatima Al-Sayed', 'fatima@vantagemat.ae', '+971-4-555-0666', 'UAE', 'Net 45', 16, 3.1, 'blacklisted', 0.40, 0.50),
]

# reliability (cancel_prob, inbound_delay_prob) for the 4 suppliers already created by seed_data
BASE_SUPPLIER_RELIABILITY = {
    'TechGlobal Inc.': (0.05, 0.10),
    'MetalWorks Ltd.': (0.12, 0.20),
    'PackSolutions':   (0.03, 0.08),
    'EuroParts GmbH':  (0.15, 0.28),
}

# sku, name, category, price, unit, reorder_point
EXTRA_PRODUCTS = [
    ('SKU-101', 'Smartphone Case', 'Electronics', 14.99, 'pcs', 40),
    ('SKU-102', 'Copper Wire 5mm', 'Raw Materials', 6.75, 'kg', 60),
    ('SKU-103', 'Bubble Wrap Roll', 'Packaging', 9.50, 'roll', 25),
    ('SKU-104', 'Server Rack Unit', 'Machinery', 890.00, 'pcs', 4),
    ('SKU-105', 'Bluetooth Speaker', 'Electronics', 45.00, 'pcs', 15),
    ('SKU-106', 'Safety Gloves (box)', 'Office Supplies', 11.25, 'box', 20),
]

# demand profile per product: base monthly units, monthly trend, seasonal amplitude/phase,
# noise, probability of an injected anomalous spike, and assigned supplier
PRODUCT_PROFILES = {
    'SKU-001': dict(base=18,  trend=0.015,  season_amp=0.15, phase=0.5, noise=0.20, anomaly=0.03, supplier='TechGlobal Inc.'),
    'SKU-002': dict(base=65,  trend=0.02,   season_amp=0.10, phase=1.0, noise=0.18, anomaly=0.04, supplier='TechGlobal Inc.'),
    'SKU-003': dict(base=420, trend=-0.005, season_amp=0.05, phase=0.0, noise=0.12, anomaly=0.02, supplier='MetalWorks Ltd.'),
    'SKU-004': dict(base=900, trend=0.01,   season_amp=0.30, phase=2.5, noise=0.15, anomaly=0.05, supplier='PackSolutions'),
    'SKU-005': dict(base=6,   trend=0.03,   season_amp=0.05, phase=0.0, noise=0.30, anomaly=0.06, supplier='MetalWorks Ltd.'),
    'SKU-006': dict(base=80,  trend=0.025,  season_amp=0.10, phase=1.5, noise=0.20, anomaly=0.03, supplier='TechGlobal Inc.'),
    'SKU-007': dict(base=55,  trend=-0.01,  season_amp=0.08, phase=0.0, noise=0.15, anomaly=0.02, supplier='PackSolutions'),
    'SKU-008': dict(base=35,  trend=0.0,    season_amp=0.05, phase=0.0, noise=0.18, anomaly=0.03, supplier='EuroParts GmbH'),
    'SKU-101': dict(base=140, trend=0.02,   season_amp=0.35, phase=3.0, noise=0.20, anomaly=0.04, supplier='Reliable Parts Co.'),
    'SKU-102': dict(base=300, trend=-0.02,  season_amp=0.05, phase=0.0, noise=0.15, anomaly=0.02, supplier='Budget Supply Chain'),
    'SKU-103': dict(base=500, trend=0.01,   season_amp=0.20, phase=2.0, noise=0.15, anomaly=0.06, supplier='PackSolutions'),
    'SKU-104': dict(base=4,   trend=0.04,   season_amp=0.10, phase=0.0, noise=0.35, anomaly=0.05, supplier='Nordic Components AB'),
    'SKU-105': dict(base=45,  trend=0.03,   season_amp=0.40, phase=3.0, noise=0.22, anomaly=0.04, supplier='Pacific Rim Traders'),
    'SKU-106': dict(base=60,  trend=0.0,    season_amp=0.05, phase=0.0, noise=0.15, anomaly=0.02, supplier='Sunrise Industrial'),
}


def _aware(d):
    return timezone.make_aware(datetime.combine(d, datetime.min.time())) + timedelta(hours=random.randint(8, 18))


class Command(BaseCommand):
    help = 'Generate months of realistic historical orders/shipments so the AI Insights models have data to train on'

    def add_arguments(self, parser):
        parser.add_argument('--months', type=int, default=15, help='How many months of history to generate')
        parser.add_argument('--clear', action='store_true', help='Delete previously generated synthetic records first')

    def handle(self, *args, **options):
        random.seed(42)
        months = options['months']

        if options['clear']:
            self._clear_synthetic()

        call_command('seed_data')

        cats = {c.name: c for c in Category.objects.all()}
        warehouses = list(Warehouse.objects.all())
        sups = {s.name: s for s in Supplier.objects.all()}

        reliability = dict(BASE_SUPPLIER_RELIABILITY)
        for name, cp, email, phone, country, terms, lead, rating, status, cancel_p, delay_p in EXTRA_SUPPLIERS:
            s, _ = Supplier.objects.get_or_create(name=name, defaults={
                'contact_person': cp, 'email': email, 'phone': phone, 'country': country,
                'payment_terms': terms, 'lead_time_days': lead, 'rating': rating, 'status': status,
            })
            sups[name] = s
            reliability[name] = (cancel_p, delay_p)

        prods = {p.sku: p for p in Product.objects.all()}
        for sku, name, cat, price, unit, reorder in EXTRA_PRODUCTS:
            p, _ = Product.objects.get_or_create(sku=sku, defaults={
                'name': name, 'category': cats[cat], 'unit_price': price, 'unit': unit, 'reorder_point': reorder,
            })
            prods[sku] = p
            Stock.objects.get_or_create(product=p, warehouse=warehouses[0], defaults={'quantity': reorder * 3})

        today = timezone.now().date()
        start = today - timedelta(days=30 * months)

        counters = {'po': 0, 'so': 0, 'trk': 0}

        with transaction.atomic():
            for sku, profile in PRODUCT_PROFILES.items():
                product = prods[sku]
                supplier = sups[profile['supplier']]
                cancel_prob, inbound_delay_prob = reliability[profile['supplier']]
                self._generate_sales_history(product, warehouses, profile, months, start, today, counters)
                self._generate_purchase_history(product, supplier, warehouses, profile, cancel_prob,
                                                 inbound_delay_prob, start, today, counters)

        self.stdout.write(self.style.SUCCESS(
            f"Generated {counters['so']} sales orders, {counters['po']} purchase orders, "
            f"{counters['trk']} shipments across {months} months of history."
        ))

    def _clear_synthetic(self):
        Shipment.objects.filter(tracking_number__startswith='TRK-SYN').delete()
        SalesOrder.objects.filter(so_number__startswith='SO-SYN').delete()
        PurchaseOrder.objects.filter(po_number__startswith='PO-SYN').delete()
        self.stdout.write('Cleared previously generated synthetic data.')

    def _generate_sales_history(self, product, warehouses, profile, months, start, today, counters):
        for m in range(months):
            month_start = start + timedelta(days=30 * m)
            trend_mult = (1 + profile['trend']) ** m
            season_mult = 1 + profile['season_amp'] * math.sin(2 * math.pi * m / 12 + profile['phase'])
            monthly_expected = max(1.0, profile['base'] * trend_mult * season_mult)

            n_events = random.randint(2, 6)
            remaining = monthly_expected
            for e in range(n_events):
                order_day = month_start + timedelta(days=random.randint(0, 29))
                if order_day > today:
                    continue

                share = remaining / (n_events - e) if e < n_events - 1 else remaining
                noise = random.gauss(1.0, profile['noise'])
                qty = max(1, round(share * max(0.3, noise)))
                if random.random() < profile['anomaly']:
                    qty = int(qty * random.uniform(4, 9))
                remaining = max(0.0, remaining - qty)

                days_since = (today - order_day).days
                if days_since > 10:
                    status = 'delivered'
                elif days_since > 4:
                    status = 'shipped'
                else:
                    status = random.choice(['pending', 'processing'])

                customer, dest = random.choice(CUSTOMERS)
                counters['so'] += 1
                so = SalesOrder.objects.create(
                    so_number=f"SO-SYN{counters['so']:05d}", customer_name=customer,
                    shipping_address=dest, warehouse=random.choice(warehouses),
                    status=status, required_date=order_day + timedelta(days=7),
                )
                SalesOrder.objects.filter(pk=so.pk).update(order_date=order_day, created_at=_aware(order_day))
                SalesOrderItem.objects.create(order=so, product=product, quantity=qty, unit_price=product.unit_price)

                if status in ('shipped', 'delivered'):
                    self._create_shipment(
                        counters, shipment_type='outbound', sales_order=so, purchase_order=None,
                        origin=random.choice(warehouses).location, destination=dest,
                        order_day=order_day, today=today,
                        final_status=('delivered' if status == 'delivered' else 'in_transit'),
                        weight_kg=round(random.uniform(0.5, 60), 2),
                    )

    def _generate_purchase_history(self, product, supplier, warehouses, profile, cancel_prob,
                                    inbound_delay_prob, start, today, counters):
        cycle_days = max(14, 30 - int(profile['base'] / 100))
        po_day = start
        while po_day <= today:
            qty = max(5, int(profile['base'] * random.uniform(1.0, 2.0)))
            cancelled = random.random() < cancel_prob
            days_since = (today - po_day).days

            if cancelled:
                po_status = 'cancelled'
            elif days_since > supplier.lead_time_days + 5:
                po_status = 'received'
            elif days_since > 2:
                po_status = 'confirmed'
            else:
                po_status = 'sent'

            counters['po'] += 1
            po = PurchaseOrder.objects.create(
                po_number=f"PO-SYN{counters['po']:05d}", supplier=supplier,
                warehouse=random.choice(warehouses), status=po_status,
                expected_date=po_day + timedelta(days=supplier.lead_time_days),
            )
            PurchaseOrder.objects.filter(pk=po.pk).update(order_date=po_day, created_at=_aware(po_day))
            unit_cost = product.cost_price if product.cost_price else Decimal(str(product.unit_price)) * Decimal('0.7')
            PurchaseOrderItem.objects.create(order=po, product=product, quantity=qty, unit_price=unit_cost)

            if po_status in ('confirmed', 'received'):
                self._create_shipment(
                    counters, shipment_type='inbound', sales_order=None, purchase_order=po,
                    origin=supplier.country or 'Overseas', destination=po.warehouse.location,
                    order_day=po_day, today=today,
                    final_status=('delivered' if po_status == 'received' else 'in_transit'),
                    weight_kg=round(qty * random.uniform(0.2, 1.5), 2),
                    transit_days=supplier.lead_time_days, delay_prob=inbound_delay_prob,
                )
            po_day += timedelta(days=cycle_days)

    def _create_shipment(self, counters, *, shipment_type, sales_order, purchase_order, origin, destination,
                          order_day, today, final_status, weight_kg, transit_days=None, delay_prob=None):
        if transit_days is None or delay_prob is None:
            carrier = random.choice(list(CARRIERS.keys()))
            cfg = CARRIERS[carrier]
            transit_days = max(1, cfg['base_transit'] + random.randint(-1, 1))
            delay_prob = cfg['delay_prob']
            delay_range = cfg['delay_range']
        else:
            carrier = random.choice(list(CARRIERS.keys()))
            delay_range = (1, 8)

        ship_date = order_day + timedelta(days=random.randint(1, 3))
        estimated_delivery = ship_date + timedelta(days=transit_days)
        actual_delivery = None
        if final_status == 'delivered':
            delayed = random.random() < delay_prob
            extra = random.randint(*delay_range) if delayed else 0
            actual_delivery = estimated_delivery + timedelta(days=extra)
            if actual_delivery > today:
                actual_delivery = today

        counters['trk'] += 1
        Shipment.objects.create(
            tracking_number=f"TRK-SYN{counters['trk']:06d}", shipment_type=shipment_type,
            sales_order=sales_order, purchase_order=purchase_order, carrier=carrier,
            status=final_status, origin=origin, destination=destination,
            ship_date=ship_date, estimated_delivery=estimated_delivery,
            actual_delivery=actual_delivery, weight_kg=weight_kg,
        )
