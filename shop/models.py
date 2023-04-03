import random
import string
from uuid import uuid4

from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from likes.models import Like
from shop.validators import validate_file_size


class Color(models.Model):
    name = models.CharField(max_length=200, null=True, blank= True )
    hex_code = models.CharField(max_length=200, null=True, blank=True)

    def __str__(self) -> str:
        if not self.name:
            return "unnamed"
        return self.name


class Size(models.Model):
    size = models.CharField(max_length=20)

    def __str__(self) -> str:
        return self.size


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
            max_digits=6, decimal_places=2
    )
    inventory = models.IntegerField(validators=[MinValueValidator(0)])
    date_posted = models.DateTimeField(auto_now_add=True)
    last_update = models.DateTimeField(auto_now=True)
    collection = models.ForeignKey(
            Collection, on_delete=models.PROTECT, related_name="products"
    )
    likes = GenericRelation(Like)
    # colors = models.ManyToManyField(Color, blank=True)
    # sizes = models.ManyToManyField(Size, blank=True)
    is_digital = models.BooleanField(default=False)
    url = models.URLField(max_length=500, null=True, blank=True)

    def __str__(self) -> str:
        return self.title

    @property
    def rating(self):
        total_reviews = self.reviews.count()
        sum_of_ratings = sum([item.ratings for item in self.reviews.all()])

        try:
            rating = float(sum_of_ratings / total_reviews)
        except ZeroDivisionError:
            rating = 1.0

        return rating

    @property
    def total_review(self):
        total = self.reviews.count()
        if total < 1:
            return 1
        return total

    class Meta:
        ordering = ["title"]


class ProductImage(models.Model):
    product = models.ForeignKey(
            Product, on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(upload_to="store/images", validators=[validate_file_size])
    # colors = models.ManyToManyField(Color, blank=True)
    # sizes = models.ManyToManyField(Size, blank=True)


class SizeInventory(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="size_inventory")
    size = models.ForeignKey(Size, on_delete=models.CASCADE, related_name="product_size")
    quantity = models.IntegerField(default=0, blank=True)
    extra_price = models.DecimalField(
            max_digits=6, decimal_places=2, blank=True, null=True
    )

    class Meta:
        verbose_name_plural = "Product Size & Inventories"

    def __str__(self):
        return self.product.title

    # def clean(self):
    #     total_quantity = self.product.size_inventory.aggregate(
    #             total_quantity=models.Sum('quantity'))['total_quantity'] or 0
    #     if total_quantity + self.quantity > self.product.inventory:
    #         raise ValidationError(
    #                 "Total quantity of this product size inventory exceeds the amount in stock.")
    #     if self.quantity == 0:
    #         raise ValidationError(
    #                 "This product size is no more in stock.")


class ColorInventory(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="color_inventory")
    color = models.ForeignKey(Color, on_delete=models.CASCADE, related_name="product_color")
    quantity = models.IntegerField(default=0, blank=True)
    extra_price = models.DecimalField(
            max_digits=6, decimal_places=2, blank=True, null=True
    )

    class Meta:
        verbose_name_plural = "Product Color & Inventories" 

    def __str__(self):
        return self.product.title

    # def clean(self):
        # total_quantity = self.product.color_inventory.aggregate(
        #         total_quantity=models.Sum('quantity'))['total_quantity'] or 0
        # if total_quantity + self.quantity > self.product.inventory:
        #     raise ValidationError(
        #             "Total quantity of this product size inventory exceeds the amount in stock.")
        # if self.quantity == 0:
        #     raise ValidationError(
        #             "This product size is no more in stock.")


class Order(models.Model):
    PAYMENT_STATUS_PENDING = "pending"
    PAYMENT_STATUS_COMPLETE = "complete"
    PAYMENT_STATUS_FAILED = "failed"
    PAYMENT_STATUS_CHOICES = [
        (PAYMENT_STATUS_PENDING, "Pending"),
        (PAYMENT_STATUS_COMPLETE, "Complete"),
        (PAYMENT_STATUS_FAILED, "Failed"),
    ]
    id = models.CharField(primary_key=True, max_length=10)
    placed_at = models.DateTimeField(auto_now_add=True)
    payment_status = models.CharField(
            max_length=10, choices=PAYMENT_STATUS_CHOICES, default=PAYMENT_STATUS_PENDING
    )
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    shipping_address = models.CharField(blank=True, null=True, max_length=1000)

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

    def get_total_price(self):
        return sum(
                [item.quantity * item.unit_price for item in self.items.all()]
        )

    class Meta:
        permissions = [("cancel_order", "Can cancel order")]
class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="items")
    product = models.ForeignKey(
            Product, on_delete=models.PROTECT, related_name="orderitems"
    )
    quantity = models.PositiveSmallIntegerField()
    unit_price = models.DecimalField(max_digits=6, decimal_places=2)
    size = models.CharField(max_length=100, null=True, blank=True)
    color = models.CharField( max_length=100, null=True, blank=True)


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
    size = models.CharField(max_length=100, null=True, blank=True)
    color = models.CharField( max_length=100, null=True, blank=True)

    # class Meta:
    #     unique_together = [["cart", "product"]]
    @property
    def resolved_price(self):
        main_price = self.product.unit_price
        colors_price =  []
        sizes_price = []

        colors = self.product.color_inventory.all()
        if colors:
            for item in colors:
                if item.extra_price:
                    colors_price.append(item.extra_price)
        
        sizes = self.product.size_inventory.all()
        if sizes:
            for item in sizes:
                if item.extra_price:
                    sizes_price.append(item.extra_price)
        
        total = main_price + sum(sizes_price) + sum(colors_price)

        return total





class Review(models.Model):
    product = models.ForeignKey(
            Product, on_delete=models.CASCADE, related_name="reviews"
    )
    rating = models.IntegerField(
            validators=[MaxValueValidator(5), MinValueValidator(1)]
    )
    description = models.TextField()
    date = models.DateField(auto_now_add=True)


class Notification(models.Model):
    NOTIFICATION_TYPE_CHOICES = (
    ("OFFER", "OFFER"),
    ("FEED", "FEED"),
    ("ACTIVITY", "ACTIVITY"),
)
    id = models.UUIDField(default=uuid4, unique=True, editable=False, primary_key=True)
    type = models.CharField(max_length=200, choices=NOTIFICATION_TYPE_CHOICES)
    title = models.CharField(max_length=200, null=True)
    desc = models.CharField(max_length=200, null=True)
    general = models.BooleanField(default=False)
    users = models.ManyToManyField(settings.AUTH_USER_MODEL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Type: {self.type}----Title: {self.title}"