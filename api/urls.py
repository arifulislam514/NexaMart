from django.urls import path, include
from product.views import ProductViewSet, CategoryViewSet, ReviewViewSet, ProductImageViewSet
from product.seller_views import SellerProductViewSet, SellerProductImageViewSet
from order.views import CartViewSet, CartItemViewSet, OrderViewset
from order.seller_views import SellerSubOrderViewSet
from sellers.views import (
    PublicStoreViewSet,
    SellerReviewViewSet,
    SellerCouponViewSet,
    ValidateCouponView
)
from rest_framework_nested import routers

router = routers.DefaultRouter()
router.register('products', ProductViewSet, basename='products')
router.register('categories', CategoryViewSet)
router.register('carts', CartViewSet, basename='carts')
router.register('orders', OrderViewset, basename='orders')
router.register('stores', PublicStoreViewSet, basename='stores')
router.register('seller/products', SellerProductViewSet, basename='seller-products')
router.register('seller/orders', SellerSubOrderViewSet, basename='seller-orders')
router.register('seller/coupons', SellerCouponViewSet, basename='seller-coupons')

store_router = routers.NestedDefaultRouter(router, 'stores', lookup='store')
store_router.register('reviews', SellerReviewViewSet, basename='store-reviews')

product_router = routers.NestedDefaultRouter(
    router, 'products', lookup='product')
product_router.register('reviews', ReviewViewSet, basename='product-review')
product_router.register('images', ProductImageViewSet,
                        basename='product-images')

seller_product_router = routers.NestedDefaultRouter(
    router, 'seller/products', lookup='product')
seller_product_router.register('images', SellerProductImageViewSet,
                               basename='seller-product-images')

cart_router = routers.NestedDefaultRouter(router, 'carts', lookup='cart')
cart_router.register('items', CartItemViewSet, basename='cart-item')

urlpatterns = [
    path('', include(router.urls)),
    path('', include(store_router.urls)),
    path('', include(product_router.urls)),
    path('', include(seller_product_router.urls)),
    path('', include(cart_router.urls)),
    path('', include('sellers.urls')),
    path('coupons/validate/', ValidateCouponView.as_view(), name='coupon-validate'),
    path('auth/', include('djoser.urls')),
    path('auth/', include('djoser.urls.jwt')),
]