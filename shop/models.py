import random
import string
from uuid import uuid4

from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from likes.models import Like
from shop.validators import validate_file_size


# TODO
class Property(models.Model):
    color = models.CharField(max_length=30, null=True, blank=True)
    size = models.IntegerField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "Properties"

    def __str__(self) -> str:
        if self.color and self.size:
            return f"{self.color - self.size}"
        elif self.color:
            return self.color
        else:
            return str(self.size)


class Collection(models.Model):
    title = models.CharField(max_length=255)
    featured_product = models.ForeignKey(
        "Product", on_delete=models.SET_NULL, null=True, related_name="+", blank=True
    )

    def __str__(self) -> str:
        return self.title

    class Meta:
        ordering = ["title"]


class Product(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    unit_price = models.DecimalField(
        max_digits=6, decimal_places=2, validators=[MinValueValidator(1)]
    )
    inventory = models.IntegerField(validators=[MinValueValidator(0)])
    date_posted = models.DateTimeField(auto_now_add=True)
    last_update = models.DateTimeField(auto_now=True)
    collection = models.ForeignKey(
        Collection, on_delete=models.PROTECT, related_name="products"
    )
    likes = GenericRelation(Like)
    property = models.ManyToManyField(Property)

    def __str__(self) -> str:
        return self.title

    class Meta:
        ordering = ["title"]


class ProductImage(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(upload_to="store/images", validators=[validate_file_size])
    property = models.ManyToManyField(Property)


class Order(models.Model):
    PAYMENT_STATUS_PENDING = "P"
    PAYMENT_STATUS_COMPLETE = "C"
    PAYMENT_STATUS_FAILED = "F"
    PAYMENT_STATUS_CHOICES = [
        (PAYMENT_STATUS_PENDING, "Pending"),
        (PAYMENT_STATUS_COMPLETE, "Complete"),
        (PAYMENT_STATUS_FAILED, "Failed"),
    ]
    id = models.CharField(primary_key=True, max_length=10)
    placed_at = models.DateTimeField(auto_now_add=True)
    payment_status = models.CharField(
        max_length=1, choices=PAYMENT_STATUS_CHOICES, default=PAYMENT_STATUS_PENDING
    )
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)


    def save(self, *args, **kwargs):
        if not self.id:
            self.id = self.id_generator()
            while __class__.objects.filter(id=self.id):
                self.id = self.id_generator()

        return super().save(*args, **kwargs)

    def id_generator(self, chars=string.digits + string.ascii_uppercase):
        length = self._meta.get_field("id").max_length
        value = "".join(random.choice(chars) for _ in range(length))

        return "#" + value

    class Meta:
        permissions = [("cancel_order", "Can cancel order")]

class TrackOrder(models.Model):
    ORDER_STATUS = [
        ("checking", "checking"),
        ("in transit", "in transit"),
        ("delivered", "delivered"),
    ]

    order = models.OneToOneField(
        Order, on_delete=models.CASCADE, related_name="tracking"
    )
    status = models.CharField(choices=ORDER_STATUS, default="checking", max_length=200)
    checking_date = models.DateTimeField(auto_now_add=True)
    in_transit_date = models.DateTimeField(null=True, blank=True)
    date_delivered = models.DateTimeField(null=True, blank=True)


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="items")
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="orderitems"
    )
    quantity = models.PositiveSmallIntegerField()
    unit_price = models.DecimalField(max_digits=6, decimal_places=2)


class BillingAddress(models.Model):
    name = models.CharField(max_length=255)
    address = models.TextField()
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)


class Cart(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4)
    created_at = models.DateTimeField(auto_now_add=True)


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])

    class Meta:
        unique_together = [["cart", "product"]]


class Review(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="reviews"
    )
    rating = models.IntegerField(
        validators=[MaxValueValidator(5), MinValueValidator(1)]
    )
    description = models.TextField()
    date = models.DateField(auto_now_add=True)
