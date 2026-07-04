from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group


ROLES = ['Admin', 'Manager', 'Warehouse', 'Procurement', 'Sales', 'Viewer']


class Command(BaseCommand):
    help = 'Create the 6 default role groups for SupplyChain Pro'

    def handle(self, *args, **options):
        for name in ROLES:
            group, created = Group.objects.get_or_create(name=name)
            if created:
                self.stdout.write(self.style.SUCCESS(f'  Created group: {name}'))
            else:
                self.stdout.write(f'  Already exists: {name}')
        self.stdout.write(self.style.SUCCESS('Done. All 6 role groups are ready.'))
