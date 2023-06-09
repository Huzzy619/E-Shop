# Generated by Django 4.1.7 on 2023-04-03 02:30

import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0010_remove_productimage_unit_price_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProductColorInventory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.IntegerField(default=0)),
                ('unit_price', models.DecimalField(decimal_places=2, max_digits=6, validators=[django.core.validators.MinValueValidator(1)])),
                ('color', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='product_color', to='shop.color')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='product_color_inventory', to='shop.product')),
            ],
            options={
                'verbose_name_plural': 'Product Size & Inventories',
            },
        ),
        migrations.CreateModel(
            name='ProductSizeInventory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.IntegerField(default=0)),
                ('unit_price', models.DecimalField(decimal_places=2, max_digits=6, validators=[django.core.validators.MinValueValidator(1)])),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='product_size_inventory', to='shop.product')),
                ('size', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='product_size', to='shop.size')),
            ],
            options={
                'verbose_name_plural': 'Product Size & Inventories',
            },
        ),
        migrations.DeleteModel(
            name='ProductSizeColorInventory',
        ),
    ]
