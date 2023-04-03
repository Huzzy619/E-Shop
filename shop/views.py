from datetime import datetime

from django.db.models.aggregates import Count
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.generics import GenericAPIView
from rest_framework.mixins import (
    CreateModelMixin,
    DestroyModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
)
from rest_framework.permissions import SAFE_METHODS, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet, ModelViewSet

from likes.models import Like
from likes.views import LikeView
from shop.pagination import DefaultPagination
from shop.permissions import IsAdminOrReadOnly

from . import serializers as shop_serializer
from .filters import ProductFilter
from .models import (
    BillingAddress,
    Cart,
    CartItem,
    Collection,
    Order,
    Product,
    ProductImage,
    Review,
    TrackOrder, Notification
)

class Notifications(GenericAPIView):
    """
    Feed, Offers, Activity Notification
    """
    permission_classes = (IsAuthenticated,)

    
    def get(self, request):
        user = request.user
        notifications = Notification.objects.filter(users__in=[user]).values(
            "type", "title", "desc", "created_at"
        )
        return Response(
            {"message": "Notified", "data": notifications, "status": True}, status=200
        )


class CollectionViewSet(ListModelMixin, RetrieveModelMixin, GenericViewSet):
    permission_classes = [IsAdminOrReadOnly]
    serializer_class = shop_serializer.CollectionSerializer
    queryset = Collection.objects.annotate(products_count=Count("products")).all()


class ProductViewSet(ListModelMixin, RetrieveModelMixin, GenericViewSet):
    queryset = Product.objects.prefetch_related("images").all()
    serializer_class = shop_serializer.ProductSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ProductFilter
    pagination_class = DefaultPagination
    permission_classes = [IsAdminOrReadOnly]
    search_fields = [
        "title",
        "description",
        "collection__name",
        # "colors__name",
        # "sizes__size",
    ]
    ordering_fields = ["unit_price", "last_update", "category"]

    def get_serializer_context(self):
        return {"request": self.request}
    
    def get_serializer_class(self):
        # Checking if the endpoint been accessed is list or retrieve
        path = self.request.get_full_path(force_append_slash=True)
        url_split = path.split("/")
        if url_split[-2].isdigit():
            return shop_serializer.SingleProductSerializer

        return super().get_serializer_class()

    @action(
        detail=False,
        methods=["GET"],
        permission_classes=[IsAuthenticated],
    )
    def my_favorites(self, request):
        products = Like.objects.objects_liked_by_user(request.user, Product)
        serializer = self.serializer_class(products, many=True)

        return Response(
            data={"products": serializer.data, "status": True},
            status=status.HTTP_200_OK,
        )


class ProductImageViewSet(ListModelMixin, RetrieveModelMixin, GenericViewSet):
    serializer_class = shop_serializer.ProductImageSerializer

    def get_serializer_context(self):
        return {"product_id": self.kwargs["product_pk"]}

    def get_queryset(self):
        return ProductImage.objects.filter(product_id=self.kwargs["product_pk"])


class LikeProductView(LikeView):
    serializer_class = shop_serializer.LikeProductSerializer

    def post(self, request):
        super().post(request)

        message = "Product marked as favorite"
        if self.unlike:
            message = "Product removed from favorite"
        return Response({"status": True, "detail": message}, status=status.HTTP_200_OK)


class ReviewViewSet(GenericViewSet):
    def get_queryset(self):
        return Review.objects.filter(product_id=self.kwargs["product_pk"])

    def get_serializer_context(self):
        return {"product_id": self.kwargs["product_pk"]}

    def get_serializer_class(self):
        if self.request.method == "POST":
            return shop_serializer.CreateReviewSerializer
        return shop_serializer.ReviewSerializer

    def create(self, request, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        data = serializer.data
        data["status"] = True
        return Response(data, status=status.HTTP_201_CREATED)

    def list(self, request, **kwargs):
        product_reviews = self.get_queryset()
        total_reviews = product_reviews.count()
        sum_of_ratings = sum([item.ratings for item in product_reviews])

        try:
            rating = float(sum_of_ratings / total_reviews)
        except ZeroDivisionError:
            rating = 1.0
            total_reviews = 1

        return Response(
            {"total_reviews": total_reviews, "rating": rating, "status": True},
            status=status.HTTP_200_OK,
        )


class CartViewSet(
    CreateModelMixin, RetrieveModelMixin, DestroyModelMixin, GenericViewSet
):
    queryset = Cart.objects.prefetch_related("items__product").all()
    serializer_class = shop_serializer.CartSerializer


class CartItemViewSet(ModelViewSet):
    http_method_names = ["get", "post", "patch", "delete"]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return shop_serializer.AddCartItemSerializer
        elif self.request.method == "PATCH":
            return shop_serializer.UpdateCartItemSerializer
        return shop_serializer.CartItemSerializer

    def get_serializer_context(self):
        return {"cart_id": self.kwargs["cart_pk"]}

    def get_queryset(self):
        return CartItem.objects.filter(cart_id=self.kwargs["cart_pk"]).select_related(
            "product"
        )


class OrderViewSet(ModelViewSet):
    http_method_names = ["get", "post", "head", "options"]

    def create(self, request, *args, **kwargs):
        serializer = shop_serializer.CreateOrderSerializer(
            data=request.data, context={"user_id": self.request.user.id}
        )
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        serializer = shop_serializer.OrderSerializer(order)
        return Response(serializer.data)

    def get_serializer_class(self):
        if self.request.method == "POST":
            return shop_serializer.CreateOrderSerializer
        elif self.request.method == "PATCH":
            return shop_serializer.UpdateOrderSerializer
        return shop_serializer.OrderSerializer

    def get_queryset(self):
        user = self.request.user

        if user.is_staff:
            return Order.objects.all()

        return Order.objects.filter(customer=user)


class TrackOrderView(GenericAPIView):
    def get_serializer_class(self):
        if self.request.method in SAFE_METHODS:
            return shop_serializer.TrackOrderSerializer
        return shop_serializer.UpdateTrackOrderSerializer

    def get(self, request, order_id):
        order = get_object_or_404(Order, id=order_id)
        serializer = self.get_serializer(order.tracking)
        data = serializer.data
        return Response(data, status=status.HTTP_200_OK)

    def patch(self, request, order_id):
        order = get_object_or_404(Order, id=order_id)
        serializer = shop_serializer.UpdateTrackOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            _status = serializer.validated_data["status"]
        except KeyError:
            return Response(
                {"message": "Invalid data", "status": False},
                status=status.HTTP_400_BAD_REQUEST,
            )

        track_obj = TrackOrder.objects.get(id=order.tracking.id)

        if _status == "in transit":
            track_obj.in_transit_date = datetime.now()
        elif _status == "delivered":
            track_obj.date_delivered = datetime.now()

            notification = Notification.objects.create(
                    type="ACTIVITY", title="Order Delivery", desc = "Your order has been delivered")
            notification.users.add(order.customer)


        track_obj.status = _status

        track_obj.save()

        return Response(
            {
                "data": shop_serializer.TrackOrderSerializer(track_obj).data,
                "status": True,
            },
            status=status.HTTP_200_OK,
        )


class AddressViewSet(ModelViewSet):
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    serializer_class = shop_serializer.AddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return BillingAddress.objects.filter(customer=self.request.user)

    def perform_create(self, serializer):
        return serializer.save(customer=self.request.user)
