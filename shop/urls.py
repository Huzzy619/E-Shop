from rest_framework_nested import routers

from . import views
from django.urls import path

router = routers.DefaultRouter(trailing_slash = False)
router.register("products", views.ProductViewSet, basename="products")
router.register("collections", views.CollectionViewSet)
router.register("address", views.AddressViewSet, basename="address")
router.register('carts', views.CartViewSet)
router.register('orders', views.OrderViewSet, basename='orders')

products_router = routers.NestedDefaultRouter(router, "products", lookup="product")
products_router.register("reviews", views.ReviewViewSet, basename="product-reviews")
products_router.register("images", views.ProductImageViewSet, basename="product-images")

carts_router = routers.NestedDefaultRouter(router, 'carts', lookup='cart')
carts_router.register('items', views.CartItemViewSet, basename='cart-items')

# URLConf
urlpatterns = [
    path('products/favorite/mark', views.LikeProductView.as_view()), 
    path('track/order/<str:order_id>', views.TrackOrderView.as_view()), 
    path("notifications", views.Notifications.as_view()),
]
urlpatterns += router.urls + products_router.urls + carts_router.urls
