from django.core.management.base import BaseCommand
from inventory.models import Category, Warehouse, Product, Stock
from suppliers.models import Supplier
from orders.models import PurchaseOrder, PurchaseOrderItem, SalesOrder, SalesOrderItem
from shipments.models import Shipment
from django.utils import timezone
import datetime


class Command(BaseCommand):
    help = 'Seed sample supply chain data'

    def handle(self, *args, **kwargs):
        self.stdout.write('Seeding data...')

        # Categories
        cats = {}
        for name in ['Electronics', 'Raw Materials', 'Packaging', 'Machinery', 'Office Supplies']:
            c, _ = Category.objects.get_or_create(name=name)
            cats[name] = c

        # Warehouses
        wh1, _ = Warehouse.objects.get_or_create(name='Main Warehouse', defaults={'location': 'Chicago, IL', 'capacity': 50000, 'manager': 'John Smith'})
        wh2, _ = Warehouse.objects.get_or_create(name='East Coast Hub', defaults={'location': 'Newark, NJ', 'capacity': 30000, 'manager': 'Sarah Lee'})
        wh3, _ = Warehouse.objects.get_or_create(name='West Coast DC', defaults={'location': 'Los Angeles, CA', 'capacity': 40000, 'manager': 'Mike Chen'})

        # Products
        products_data = [
            ('SKU-001', 'Laptop Pro 15"', 'Electronics', 1299.99, 'pcs', 5),
            ('SKU-002', 'Wireless Mouse', 'Electronics', 29.99, 'pcs', 20),
            ('SKU-003', 'Steel Rod 10mm', 'Raw Materials', 4.50, 'kg', 100),
            ('SKU-004', 'Cardboard Box L', 'Packaging', 1.20, 'pcs', 200),
            ('SKU-005', 'Industrial Motor', 'Machinery', 450.00, 'pcs', 3),
            ('SKU-006', 'USB-C Cable 2m', 'Electronics', 12.99, 'pcs', 50),
            ('SKU-007', 'Printer Paper A4', 'Office Supplies', 8.50, 'ream', 30),
            ('SKU-008', 'Aluminum Sheet', 'Raw Materials', 22.00, 'sheet', 15),
        ]
        prods = {}
        for sku, name, cat, price, unit, reorder in products_data:
            p, _ = Product.objects.get_or_create(sku=sku, defaults={
                'name': name, 'category': cats[cat], 'unit_price': price, 'unit': unit, 'reorder_point': reorder
            })
            prods[sku] = p

        # Stock
        stock_data = [
            ('SKU-001', wh1, 8), ('SKU-001', wh2, 3), ('SKU-002', wh1, 45),
            ('SKU-003', wh1, 80), ('SKU-003', wh3, 120), ('SKU-004', wh1, 350),
            ('SKU-005', wh2, 2), ('SKU-006', wh1, 60), ('SKU-006', wh3, 25),
            ('SKU-007', wh1, 12), ('SKU-008', wh2, 10),
        ]
        for sku, wh, qty in stock_data:
            Stock.objects.get_or_create(product=prods[sku], warehouse=wh, defaults={'quantity': qty})

        # Suppliers
        sup_data = [
            ('TechGlobal Inc.', 'Alice Wong', 'alice@techglobal.com', '+1-312-555-0101', 'USA', 'Net 30', 7, 4.5),
            ('MetalWorks Ltd.', 'Bob Patel', 'bob@metalworks.co.uk', '+44-20-555-0202', 'UK', 'Net 45', 14, 4.2),
            ('PackSolutions', 'Carlos Ruiz', 'carlos@packsol.mx', '+52-55-555-0303', 'Mexico', 'Net 15', 5, 4.8),
            ('EuroParts GmbH', 'Heidi Müller', 'heidi@europarts.de', '+49-30-555-0404', 'Germany', 'Net 60', 21, 3.9),
        ]
        sups = {}
        for name, cp, email, phone, country, terms, lead, rating in sup_data:
            s, _ = Supplier.objects.get_or_create(name=name, defaults={
                'contact_person': cp, 'email': email, 'phone': phone,
                'country': country, 'payment_terms': terms, 'lead_time_days': lead, 'rating': rating
            })
            sups[name] = s

        # Purchase Orders
        today = datetime.date.today()
        po1, created = PurchaseOrder.objects.get_or_create(po_number='PO-A1B2C3D4', defaults={
            'supplier': sups['TechGlobal Inc.'], 'warehouse': wh1,
            'status': 'confirmed', 'expected_date': today + datetime.timedelta(days=7)
        })
        if created:
            PurchaseOrderItem.objects.create(order=po1, product=prods['SKU-001'], quantity=10, unit_price=1100)
            PurchaseOrderItem.objects.create(order=po1, product=prods['SKU-002'], quantity=50, unit_price=22)

        po2, created = PurchaseOrder.objects.get_or_create(po_number='PO-E5F6G7H8', defaults={
            'supplier': sups['MetalWorks Ltd.'], 'warehouse': wh2,
            'status': 'received', 'expected_date': today - datetime.timedelta(days=3)
        })
        if created:
            PurchaseOrderItem.objects.create(order=po2, product=prods['SKU-003'], quantity=500, unit_price=4.00)
            PurchaseOrderItem.objects.create(order=po2, product=prods['SKU-008'], quantity=30, unit_price=19.50)

        po3, created = PurchaseOrder.objects.get_or_create(po_number='PO-I9J0K1L2', defaults={
            'supplier': sups['PackSolutions'], 'warehouse': wh1,
            'status': 'draft', 'expected_date': today + datetime.timedelta(days=14)
        })
        if created:
            PurchaseOrderItem.objects.create(order=po3, product=prods['SKU-004'], quantity=1000, unit_price=1.00)

        # Sales Orders
        so1, created = SalesOrder.objects.get_or_create(so_number='SO-AA11BB22', defaults={
            'customer_name': 'Acme Corporation', 'customer_email': 'orders@acme.com',
            'shipping_address': '123 Business Ave, New York, NY 10001',
            'warehouse': wh1, 'status': 'processing',
            'required_date': today + datetime.timedelta(days=5)
        })
        if created:
            SalesOrderItem.objects.create(order=so1, product=prods['SKU-001'], quantity=2, unit_price=1299.99)
            SalesOrderItem.objects.create(order=so1, product=prods['SKU-002'], quantity=5, unit_price=29.99)

        so2, created = SalesOrder.objects.get_or_create(so_number='SO-CC33DD44', defaults={
            'customer_name': 'Beta Industries', 'customer_email': 'purchasing@beta.com',
            'shipping_address': '456 Industrial Blvd, Houston, TX 77001',
            'warehouse': wh2, 'status': 'shipped',
            'required_date': today + datetime.timedelta(days=2)
        })
        if created:
            SalesOrderItem.objects.create(order=so2, product=prods['SKU-006'], quantity=20, unit_price=12.99)

        so3, created = SalesOrder.objects.get_or_create(so_number='SO-EE55FF66', defaults={
            'customer_name': 'Gamma Tech', 'customer_email': 'tech@gamma.io',
            'shipping_address': '789 Tech Park, San Francisco, CA 94102',
            'warehouse': wh3, 'status': 'delivered',
            'required_date': today - datetime.timedelta(days=5)
        })
        if created:
            SalesOrderItem.objects.create(order=so3, product=prods['SKU-005'], quantity=1, unit_price=450.00)

        so4, created = SalesOrder.objects.get_or_create(so_number='SO-GG77HH88', defaults={
            'customer_name': 'Delta Logistics', 'warehouse': wh1, 'status': 'pending'
        })
        if created:
            SalesOrderItem.objects.create(order=so4, product=prods['SKU-007'], quantity=10, unit_price=8.50)

        # Shipments
        Shipment.objects.get_or_create(tracking_number='TRK-FX1234567890', defaults={
            'shipment_type': 'outbound', 'sales_order': so2, 'carrier': 'FedEx',
            'status': 'in_transit', 'origin': 'Newark, NJ', 'destination': 'Houston, TX',
            'ship_date': today - datetime.timedelta(days=1),
            'estimated_delivery': today + datetime.timedelta(days=2), 'weight_kg': 5.2
        })
        Shipment.objects.get_or_create(tracking_number='TRK-UPS9876543210', defaults={
            'shipment_type': 'inbound', 'purchase_order': po1, 'carrier': 'UPS',
            'status': 'pending', 'origin': 'Shenzhen, China', 'destination': 'Chicago, IL',
            'estimated_delivery': today + datetime.timedelta(days=10), 'weight_kg': 42.0
        })
        Shipment.objects.get_or_create(tracking_number='TRK-DHL1122334455', defaults={
            'shipment_type': 'outbound', 'sales_order': so3, 'carrier': 'DHL',
            'status': 'delivered', 'origin': 'Los Angeles, CA', 'destination': 'San Francisco, CA',
            'ship_date': today - datetime.timedelta(days=7),
            'estimated_delivery': today - datetime.timedelta(days=5),
            'actual_delivery': today - datetime.timedelta(days=5), 'weight_kg': 18.5
        })

        self.stdout.write(self.style.SUCCESS('Sample data seeded successfully!'))
