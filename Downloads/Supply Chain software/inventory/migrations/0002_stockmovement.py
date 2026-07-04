import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='cost_price',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.CreateModel(
            name='StockMovement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('movement_type', models.CharField(
                    choices=[('in', 'Stock In'), ('out', 'Stock Out'), ('adjustment', 'Adjustment')],
                    max_length=20,
                )),
                ('quantity', models.IntegerField()),
                ('reference_type', models.CharField(blank=True, max_length=50)),
                ('reference_number', models.CharField(blank=True, max_length=100)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.CharField(blank=True, default='System', max_length=100)),
                ('product', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='movements',
                    to='inventory.product',
                )),
                ('warehouse', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='movements',
                    to='inventory.warehouse',
                )),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]
