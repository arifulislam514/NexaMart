from decimal import Decimal
from django.db.models import Sum
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.viewsets import ReadOnlyModelViewSet, ModelViewSet
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from sellers.models import SellerProfile, SellerReview, SellerCoupon
from sellers.permissions import IsApprovedSeller
from sellers.serializers import (
    SellerProfileSerializer,
    SellerApplicationSerializer,
    PublicStoreDetailSerializer,
    SellerEarningsSerializer,
    SellerReviewSerializer,
    SellerCouponSerializer,
    CouponValidateSerializer
)
from product.models import Product
from product.serializers import ProductSerializer
from product.paginations import DefaultPagination
from order.models import SubOrder


class ApplySellerView(APIView):
    """
    Endpoint for an authenticated buyer to apply to become a seller.
    Initial status will be 'pending'.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if hasattr(request.user, 'seller_profile'):
            profile = request.user.seller_profile
            return Response(
                {
                    "detail": f"You already have a seller application in '{profile.status}' status.",
                    "seller_profile": SellerProfileSerializer(profile).data
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = SellerApplicationSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        seller_profile = serializer.save()
        return Response(
            {
                "message": "Your seller application has been submitted and is currently pending approval.",
                "seller_profile": SellerProfileSerializer(seller_profile).data
            },
            status=status.HTTP_201_CREATED
        )


class SellerProfileDetailView(RetrieveUpdateAPIView):
    """
    Allows the logged-in seller to view and update their own store details.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = SellerProfileSerializer

    def get_object(self):
        if not hasattr(self.request.user, 'seller_profile'):
            return None
        return self.request.user.seller_profile

    def get(self, request, *args, **kwargs):
        instance = self.get_object()
        if not instance:
            return Response(
                {"detail": "You do not have a seller profile. Apply to become a seller first."},
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def patch(self, request, *args, **kwargs):
        instance = self.get_object()
        if not instance:
            return Response(
                {"detail": "You do not have a seller profile."},
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def put(self, request, *args, **kwargs):
        return self.patch(request, *args, **kwargs)


class SellerEarningsView(APIView):
    """
    Returns financial earnings and order metrics for the logged-in approved seller.
    """
    permission_classes = [IsApprovedSeller]

    def get(self, request):
        seller = request.user.seller_profile
        sub_orders = SubOrder.objects.filter(seller=seller)

        total_sub_orders = sub_orders.count()
        delivered_sub_orders = sub_orders.filter(status=SubOrder.STATUS_DELIVERED).count()
        canceled_sub_orders = sub_orders.filter(status=SubOrder.STATUS_CANCELED).count()
        pending_sub_orders = sub_orders.exclude(
            status__in=[SubOrder.STATUS_DELIVERED, SubOrder.STATUS_CANCELED]
        ).count()

        delivered_aggregates = sub_orders.filter(status=SubOrder.STATUS_DELIVERED).aggregate(
            total_revenue=Sum('subtotal'),
            total_commission=Sum('commission_amount'),
            net_earnings=Sum('seller_earning')
        )

        pending_aggregates = sub_orders.exclude(
            status__in=[SubOrder.STATUS_DELIVERED, SubOrder.STATUS_CANCELED]
        ).aggregate(
            pending_earnings=Sum('seller_earning')
        )

        data = {
            "total_sub_orders": total_sub_orders,
            "delivered_sub_orders": delivered_sub_orders,
            "pending_sub_orders": pending_sub_orders,
            "canceled_sub_orders": canceled_sub_orders,
            "total_revenue": delivered_aggregates['total_revenue'] or Decimal('0.00'),
            "total_commission_paid": delivered_aggregates['total_commission'] or Decimal('0.00'),
            "net_earnings": delivered_aggregates['net_earnings'] or Decimal('0.00'),
            "pending_earnings": pending_aggregates['pending_earnings'] or Decimal('0.00'),
        }
        serializer = SellerEarningsSerializer(data)
        return Response(serializer.data)


class PublicStoreViewSet(ReadOnlyModelViewSet):
    """
    Public storefront viewset for customers to view store profiles and products.
    """
    queryset = SellerProfile.objects.filter(status=SellerProfile.STATUS_APPROVED)
    serializer_class = PublicStoreDetailSerializer
    lookup_field = 'slug'

    @action(detail=True, methods=['get'])
    def products(self, request, slug=None):
        store = self.get_object()
        products = Product.objects.filter(seller=store).select_related('category').prefetch_related('images')
        paginator = DefaultPagination()
        page = paginator.paginate_queryset(products, request)
        if page is not None:
            serializer = ProductSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        serializer = ProductSerializer(products, many=True)
        return Response(serializer.data)


class SellerReviewViewSet(ModelViewSet):
    """
    ViewSet for customer reviews of a specific store.
    """
    serializer_class = SellerReviewSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    pagination_class = DefaultPagination

    def get_seller(self):
        store_slug = self.kwargs.get('store_slug')
        try:
            return SellerProfile.objects.get(slug=store_slug, status=SellerProfile.STATUS_APPROVED)
        except SellerProfile.DoesNotExist:
            raise NotFound("Store not found or not approved.")

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return SellerReview.objects.none()
        seller = self.get_seller()
        return SellerReview.objects.filter(seller=seller).select_related('user')

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if getattr(self, 'swagger_fake_view', False):
            return context
        context['seller'] = self.get_seller()
        return context

    def perform_destroy(self, instance):
        if not self.request.user.is_staff and instance.user != self.request.user:
            raise PermissionDenied("You can only delete your own review.")
        instance.delete()

    def perform_update(self, serializer):
        if not self.request.user.is_staff and serializer.instance.user != self.request.user:
            raise PermissionDenied("You can only edit your own review.")
        serializer.save()


class SellerCouponViewSet(ModelViewSet):
    """
    CRUD API for approved sellers to create and manage store coupons.
    """
    serializer_class = SellerCouponSerializer
    permission_classes = [IsApprovedSeller]
    pagination_class = DefaultPagination

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return SellerCoupon.objects.none()
        seller = self.request.user.seller_profile
        return SellerCoupon.objects.filter(seller=seller)

    def perform_create(self, serializer):
        serializer.save(seller=self.request.user.seller_profile)


class ValidateCouponView(APIView):
    """
    Validates a coupon code against a store and cart purchase amount.
    """
    def post(self, request):
        serializer = CouponValidateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        code = serializer.validated_data['code'].strip().upper()
        store_slug = serializer.validated_data.get('store_slug')
        cart_amount = serializer.validated_data['cart_amount']

        coupon_query = SellerCoupon.objects.filter(code__iexact=code, active=True)
        if store_slug:
            coupon_query = coupon_query.filter(seller__slug=store_slug)

        coupon = coupon_query.select_related('seller').first()
        if not coupon:
            return Response(
                {"valid": False, "detail": "Invalid or inactive coupon code."},
                status=status.HTTP_404_NOT_FOUND
            )

        if not coupon.is_valid_now():
            return Response(
                {"valid": False, "detail": "This coupon has expired or is not yet active."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if cart_amount < coupon.min_purchase:
            return Response(
                {
                    "valid": False,
                    "detail": f"Minimum purchase amount of {coupon.min_purchase} required for this coupon.",
                    "min_purchase": coupon.min_purchase
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        discount_amount = coupon.calculate_discount(cart_amount)
        final_amount = max(Decimal('0.00'), cart_amount - discount_amount)

        return Response(
            {
                "valid": True,
                "code": coupon.code,
                "store_name": coupon.seller.store_name,
                "store_slug": coupon.seller.slug,
                "discount_type": coupon.discount_type,
                "discount_value": coupon.discount_value,
                "discount_amount": discount_amount,
                "cart_amount": cart_amount,
                "final_amount": final_amount
            },
            status=status.HTTP_200_OK
        )
