from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0002_stockmovement'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='barcode',
            field=models.CharField(blank=True, default='', help_text='EAN/UPC barcode (leave blank to use SKU)', max_length=100),
        ),
    ]
