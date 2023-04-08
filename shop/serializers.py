from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers

from likes.models import Like
from likes.serializers import LikeSerializer
from shop.signals import order_created

from .models import (
    BillingAddress,
    Cart,
    CartItem,  # SizeInventory,
    Collection,
    Color,
    ColorSizeInventory,
    Order,
    OrderItem,
    Product,
    ProductImage,
    Review,
    Size,
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


class ColorSizeInventorySerializer(serializers.ModelSerializer):
    size = SizeSerializer()
    color = ColorSerializer()

    class Meta:
        model = ColorSizeInventory
        fields = ["id", "quantity", "extra_price", "size", "color"]


class ProductSerializer(serializers.ModelSerializer):
    properties = ColorSizeInventorySerializer(
        source="color_size_inventory", many=True, read_only=True
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
            "properties",
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
    inventory = serializers.SerializerMethodField()

    def get_total_price(self, cart_item: CartItem):
        return cart_item.quantity * cart_item.resolved_price

    def get_inventory(self, cart_item: CartItem):
        queryset = ColorSizeInventory.objects.filter(
            product_id=cart_item.product.id,
        ).select_related("color", "size")
        # queryset = cart_item.product.color_size_inventory

        if cart_item.color and cart_item.size:
            queryset = queryset.filter(
                color__name=cart_item.color,
                size__size=cart_item.size,
            )
        elif cart_item.color:
            queryset = queryset.filter(color__name=cart_item.color)
        elif cart_item.size:
            queryset = queryset.filter(size__size=cart_item.size)
        else:
            return cart_item.product.inventory

        obj = queryset.first()
        if obj:
            return obj.quantity

        return None

    class Meta:
        model = CartItem
        fields = [
            "id",
            "product",
            "quantity",
            "inventory",
            "size",
            "color",
            "hex_code",
            "total_price",
        ]


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
        product_id = attrs["product_id"]
        requested_quantity = attrs["quantity"]
        inventory = 0

        size = Size.objects.filter(size=attrs.get("size")).first()
        if attrs.get("size") and not size:
            raise serializers.ValidationError(
                {"message": "Invalid size object", "status": False}
            )

        color = Color.objects.filter(name=attrs.get("color")).first()
        if attrs.get("color") and not color:
            raise serializers.ValidationError(
                {"message": "Invalid color object", "status": False}
            )

        if not ColorSizeInventory.objects.filter(
            color=color, product_id=product_id, size=size
        ):
            raise serializers.ValidationError(
                {
                    "message": "We don't have that color and size for this specific product!",
                    "status": False,
                }
            )

        queryset = ColorSizeInventory.objects.filter(
            product_id=product_id,
        ).select_related("color", "size")

        if color and size:
            queryset = queryset.filter(
                color__name=color.name,
                size__size=size.size,
            )
        elif color:
            queryset = queryset.filter(color__name=color.name)
        elif size:
            queryset = queryset.filter(size__size=size.size)
        else:
            product = Product.objects.get(pk=product_id)
            inventory = product.inventory

        obj = queryset.first()
        if obj:
            inventory = obj.quantity

        if requested_quantity > inventory:
            raise serializers.ValidationError(
                {"message": "Not enough of this product to add to cart", "status": False}
            )

        return super().validate(attrs)
    

    def create(self, validated_data):
        cart_id = self.context["cart_id"]
        product_id = validated_data["product_id"]
        quantity = validated_data["quantity"]
        size = validated_data.get("size", "")
        color = validated_data.get("color", "")

        
        color_name = None
        
        if color:
            color_name = Color.objects.filter(name=color).first()

        instance, created = CartItem.objects.get_or_create(
            cart_id=cart_id,
            product_id=product_id,
            size=size if size else None,
            color=color_name if color else None,
            defaults={
                "quantity": quantity,
                "hex_code": color_name.hex_code if color else None
            },
        )

        if not created:
            # item already exists in cart, update quantity
            instance.quantity = quantity
            instance.save()

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
                    hex_code = item.hex_code,
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
