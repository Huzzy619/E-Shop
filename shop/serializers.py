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


class ColorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Color
        fields = ["name", "hex_code"]


class SizeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Size
        fields = ["size"]


class SizeInventorySerializer(serializers.ModelSerializer):
    size = SizeSerializer()

    class Meta:
        model = SizeInventory
        fields = ["quantity", "extra_price", "size"]


class ColorInventorySerializer(serializers.ModelSerializer):
    color = ColorSerializer()

    class Meta:
        model = ColorInventory
        fields = ["quantity", "extra_price", "color"]


class ProductSerializer(serializers.ModelSerializer):
    sizes = SizeInventorySerializer(source="size_inventory", many=True, read_only=True)
    colors = ColorInventorySerializer(
        source="color_inventory", many=True, read_only=True
    )
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
            "colors",
            "sizes",
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
    images = ProductImageSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = ["id", "title", "unit_price", "product_url", "images"]

    def get_product_url(self, product):
        if product.is_digital:
            return product.url
        return None

    def to_representation(self, instance):
        # ? Override the way the objects are presented, trying to get only the first image
        rep = super().to_representation(instance)

        try:
            rep["images"] = [rep["images"][0]]
        except IndexError:
            pass
        return rep


class CartItemSerializer(serializers.ModelSerializer):
    product = SimpleProductSerializer()
    total_price = serializers.SerializerMethodField()

    def get_total_price(self, cart_item: CartItem):
        return cart_item.quantity * cart_item.resolved_price

    class Meta:
        model = CartItem
        fields = ["id", "product", "quantity", "size", "color", "total_price"]


class CartSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(read_only=True)
    items = CartItemSerializer(many=True, read_only=True)
    cart_total_price = serializers.SerializerMethodField()

    def get_cart_total_price(self, cart):
        return sum([item.quantity * item.resolved_price for item in cart.items.all()])

    class Meta:
        model = Cart
        fields = ["id", "items", "cart_total_price"]


class AddCartItemSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField()
    size = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    color = serializers.CharField(required=False, allow_null=True, allow_blank=True)
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

            if not SizeInventory.objects.filter(
                size=size, product_id=attrs["product_id"]
            ):
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

        # Check if item already in cart to avoid duplicates
        instance = CartItem.objects.filter(
            cart_id=cart_id,
            product_id=product_id,
            size=size if size else None,
            color=color if color else None,
        )

        if instance:
            # update quantity to the currently passed value
            instance.quantity += quantity
            instance.save()

        else:
            instance = CartItem.objects.create(
                cart_id=cart_id,
                product_id=product_id,
                quantity=quantity,
                size=size if size else None,
                color=color if color else None,
            )

        return instance

    class Meta:
        model = CartItem
        fields = ["id", "product_id", "quantity", "size", "color"]


class UpdateCartItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = CartItem
        fields = ["quantity"]


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
            raise serializers.ValidationError(
                {"message": "No cart with the given ID was found.", "status": False}
            )
        if CartItem.objects.filter(cart_id=cart_id).count() == 0:
            raise serializers.ValidationError(
                {"message": "The cart is empty.", "status": False}
            )
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
                    unit_price=item.resolved_price,
                    quantity=item.quantity,
                    size=item.size,
                    color=item.color,
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
