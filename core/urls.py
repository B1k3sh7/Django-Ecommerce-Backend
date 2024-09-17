from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import *

router = DefaultRouter()

router.register(r'categories', CategoryViewSet)
router.register(r'brands', BrandViewSet)
router.register(r'products', ProductViewSet)
router.register(r'orders', OrderViewSet)
router.register(r'order-items', OrderItemViewSet)
router.register(r'reviews', ReviewViewSet)
router.register(r'carts', CartViewSet)
router.register(r'cart-items', CartItemViewSet)


router.register(r'shipping-methods', ShippingMethodViewSet)
router.register(r'shipping-details', ShippingDetailViewSet)


urlpatterns = [
    path('', include(router.urls)),
]
