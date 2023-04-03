from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers

from likes.models import Like
from likes.serializers import LikeSerializer
from shop.signals import order_created

from .models import (
    BillingAddress,
    Cart,
    CartItem,
    Collection,
    Color,
    ColorInventory,
    Order,
    OrderItem,
    Product,
    ProductImage,
    Review,
    Size,
    SizeInventory,
    TrackOrder,
)

Customer = get_user_model()


class CollectionSerializer(serializers.ModelSerializer):
    products_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Collection
        fields = ["id", "title", "products_count"]


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ["id", "image"]


class SingleProductSerializer(serializers.ModelSerializer):
    images = ProductImageSerializer(many=True, read_only=True)
    sizes = serializers.SerializerMethodField()
    colors = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "title",
            "description",
            "is_digital",
            "inventory",
            "unit_price",
            "collection",
            "rating",
            "total_review",
            "images",
            "colors",
            "sizes",
        ]
        depth = 1

    def get_sizes(self, product: Product):
        values = product.size_inventory.values("unit_price", "size__size", "quantity")

        if values:
            return values
        return []

    def get_colors(self, product: Product):
        values = product.color_inventory.values(
            "unit_price", "color__name", "color__hex_code", "quantity"
        )

        if values:
            return values

        return []


class ProductSerializer(serializers.ModelSerializer):
    images = ProductImageSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "title",
            "description",
            "is_digital",
            "inventory",
            "unit_price",
            "collection",
            "rating",
            "total_review",
            "images",
        ]


class LikeProductSerializer(LikeSerializer):
    product_id = serializers.IntegerField(source="object_id")
    model = Product

    class Meta:
        model = Like
        fields = ["id", "product_id"]


class CreateReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = ["rating", "description"]

    def create(self, validated_data):
        product_id = self.context["product_id"]
        return Review.objects.create(product_id=product_id, **validated_data)


class ReviewSerializer(serializers.Serializer):
    total_reviews = serializers.IntegerField()
    rating = serializers.FloatField()


class SimpleProductSerializer(serializers.ModelSerializer):
    product_url = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ["id", "title", "unit_price", "product_url"]

    def get_product_url(self, product):
        if product.is_digital:
            return product.url
        return None


class CartItemSerializer(serializers.ModelSerializer):
    product = SimpleProductSerializer()
    total_price = serializers.SerializerMethodField()

    def get_total_price(self, cart_item: CartItem):
        return cart_item.quantity * cart_item.product.unit_price

    class Meta:
        model = CartItem
        fields = ["id", "product", "quantity", "total_price"]


class CartSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(read_only=True)
    items = CartItemSerializer(many=True, read_only=True)
    total_price = serializers.SerializerMethodField()

    def get_total_price(self, cart):
        return sum(
            [item.quantity * item.product.unit_price for item in cart.items.all()]
        )

    class Meta:
        model = Cart
        fields = ["id", "items", "total_price"]


class AddCartItemSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField()
    size = serializers.CharField(required=False)
    color = serializers.CharField(required=False)
    quantity = serializers.IntegerField()

    def validate_product_id(self, value):
        if not Product.objects.filter(pk=value).exists():
            raise serializers.ValidationError(
                {"message": "No product with the given ID was found."}
            )
        return value

    def validate(self, attrs):
        if size := attrs.get("size", ""):
            try:
                size = Size.objects.get(size=size)
            except Size.DoesNotExist:
                raise serializers.ValidationError(
                    {"message": "Invalid size object", "status": False}
                )

            if not SizeInventory.objects.filter(size=size, product_id=attrs["product_id"]):
                raise serializers.ValidationError(
                    {
                        "message": "We don't have that size for this specific product!",
                        "status": False,
                    }
                )

        if color := attrs.get("color", ""):

            try:
                color = Color.objects.get(name=color)
            except Color.DoesNotExist:
                raise serializers.ValidationError(
                    {"message": "Invalid color object", "status": False}
                )


            if not ColorInventory.objects.filter(
                color=color, product_id=attrs["product_id"]
            ):
                raise serializers.ValidationError(
                    {
                        "message": "We don't have that color for this specific product!",
                        "status": False,
                    }
                )
        return super().validate(attrs)


    def create(self, validated_data):
        cart_id = self.context["cart_id"]
        product_id = validated_data["product_id"]
        quantity = validated_data["quantity"]
        size = validated_data.get("size", "")
        color = validated_data.get("color", "")

        self.instance = CartItem.objects.create(
                cart_id=cart_id,
                product_id=product_id,
                quantity = quantity,
                size=size if size else None,
                color=color if color else None,
            )

        return self.instance
    class Meta:
        model = CartItem
        fields = ["id", "product_id", "quantity", "size", "color"]


class UpdateCartItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = CartItem
        fields = ["quantity", "size", "color"]
    


class CustomerSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(read_only=True) 

    class Meta:
        model = Customer
        fields = ["id"]


class OrderItemSerializer(serializers.ModelSerializer):
    product = SimpleProductSerializer()

    class Meta:
        model = OrderItem
        fields = ["id", "product", "unit_price", "quantity"]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)

    class Meta:
        model = Order
        fields = ["id", "customer", "placed_at", "payment_status", "items"]


class UpdateOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ["payment_status"]


class CreateOrderSerializer(serializers.Serializer):
    cart_id = serializers.UUIDField()

    def validate_cart_id(self, cart_id):
        if not Cart.objects.filter(pk=cart_id).exists():
            raise serializers.ValidationError("No cart with the given ID was found.")
        if CartItem.objects.filter(cart_id=cart_id).count() == 0:
            raise serializers.ValidationError("The cart is empty.")
        return cart_id

    def save(self, **kwargs):
        with transaction.atomic():
            cart_id = self.validated_data["cart_id"]

            cart_items = CartItem.objects.select_related("product").filter(
                cart_id=cart_id
            )
            # Check the quantities been ordered compared with the inventory
            for item in cart_items:
                item.product.inventory -= item.quantity

                if item.product.inventory < 0:
                    raise serializers.ValidationError(
                        {
                            "message": "There is not enough product to complete the order",
                            "status": False,
                            "detail": {
                                "id": item.product.id,
                                "product": item.product.title,
                            },
                        }
                    )

            customer = Customer.objects.get(id=self.context["user_id"])
            order = Order.objects.create(customer=customer)

            order_items = [
                OrderItem(
                    order=order,
                    product=item.product,
                    unit_price=item.product.unit_price,
                    quantity=item.quantity,
                    size = item.size,
                    color = item.color
                )
                for item in cart_items
            ]
            OrderItem.objects.bulk_create(order_items)

            Cart.objects.filter(pk=cart_id).delete()
            order_created.send_robust(self.__class__, instance=order)

            return order


class TrackOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrackOrder
        exclude = ["id", "order"]


class UpdateTrackOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrackOrder
        fields = ["status"]


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillingAddress
        fields = ["id", "name", "address"]
