# Generated by Django 4.1.7 on 2023-04-01 07:50

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("shop", "0006_product_is_digital_product_url"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="shipping_address",
            field=models.CharField(blank=True, max_length=1000, null=True),
        ),
    ]
