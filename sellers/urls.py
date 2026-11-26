from django.urls import path
from sellers.views import (
    ApplySellerView,
    SellerProfileDetailView,
    SellerEarningsView
)

urlpatterns = [
    path('sellers/apply/', ApplySellerView.as_view(), name='seller-apply'),
    path('seller/profile/', SellerProfileDetailView.as_view(), name='seller-profile'),
    path('seller/earnings/', SellerEarningsView.as_view(), name='seller-earnings'),
]
