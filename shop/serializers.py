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
    Order,
    OrderItem,
    Product,
    ProductImage,
    Review,
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

    


class ProductSerializer(serializers.ModelSerializer):
    images = ProductImageSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "title",
            "description",
            "inventory",
            "unit_price",
            "collection",
            "images",
            "rating",
            "total_review",
            # "colors",
            # "sizes",
        ]
        depth = 1


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
    product_url  = serializers.SerializerMethodField()
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


class AddCartItemSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    size = serializers.IntegerField(required = False)
    color = serializers.CharField(required = False)
    quantity = serializers.IntegerField()

    def validate_product_id(self, value):
        if not Product.objects.filter(pk=value).exists():
            raise serializers.ValidationError(
                {"message": "No product with the given ID was found."}
            )
        return value
    
    def validate(self, attrs):
        product  = Product.objects.filter(pk = attrs['product_id'])
        if attrs['size']:
            
            pass
        return super().validate(attrs)

    def save(self, **kwargs):
        cart_id = self.context["cart_id"]
        product_id = self.validated_data["product_id"]
        quantity = self.validated_data["quantity"]
        size = self.validated_data["size"]
        color_name = self.validated_data["color"]

        try:
            cart_item = CartItem.objects.get(
            cart_id=cart_id, product_id=product_id, size = size, color = color_name)
            cart_item.quantity += quantity
            cart_item.save()
            self.instance = cart_item

        except CartItem.DoesNotExist:
            from .models import Size, Color
            self.instance = CartItem.objects.create(
                cart_id=cart_id,
                product_id=product_id, 
                size = Size.objects.get(size = size), 
                color = Color.objects.get(name = color_name), 

            )

        return self.instance

    # class Meta:
    #     model = CartItem
    #     fields = ["id", "product_id", "quantity"]


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
            #Check the quantities been ordered compared with the inventory
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
