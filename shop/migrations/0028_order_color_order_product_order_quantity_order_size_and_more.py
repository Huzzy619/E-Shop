# Generated by Django 4.2 on 2023-04-10 10:06

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("shop", "0027_remove_order_item_remove_orderitem_id_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="color",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name="order",
            name="product",
            field=models.ForeignKey(
                default=1,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="orderitems",
                to="shop.product",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="order",
            name="quantity",
            field=models.PositiveSmallIntegerField(default=1),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="order",
            name="size",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name="order",
            name="unit_price",
            field=models.DecimalField(decimal_places=2, default=1, max_digits=6),
            preserve_default=False,
        ),
        migrations.DeleteModel(
            name="OrderItem",
        ),
    ]
