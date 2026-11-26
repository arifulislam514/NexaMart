from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status, serializers
from order.models import SubOrder, OrderItem
from order.serializers import OrderItemSerializer
from order.services import OrderService
from product.paginations import DefaultPagination
from sellers.permissions import IsApprovedSeller


class SellerSubOrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'product_name', 'price', 'quantity', 'total_price']


class SellerSubOrderDetailSerializer(serializers.ModelSerializer):
    items = SellerSubOrderItemSerializer(many=True, read_only=True)
    buyer_email = serializers.EmailField(source='order.user.email', read_only=True)
    buyer_name = serializers.SerializerMethodField()
    buyer_address = serializers.CharField(source='order.user.address', read_only=True)
    buyer_phone = serializers.CharField(source='order.user.phone_number', read_only=True)
    order_created_at = serializers.DateTimeField(source='order.created_at', read_only=True)

    class Meta:
        model = SubOrder
        fields = [
            'id', 'order', 'status', 'tracking_number', 'subtotal',
            'commission_rate', 'commission_amount', 'seller_earning',
            'created_at', 'order_created_at', 'buyer_email', 'buyer_name',
            'buyer_phone', 'buyer_address', 'items'
        ]
        read_only_fields = fields

    def get_buyer_name(self, obj):
        user = obj.order.user
        return f"{user.first_name} {user.last_name}".strip() or user.email


class UpdateSubOrderStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=SubOrder.STATUS_CHOICES)
    tracking_number = serializers.CharField(required=False, allow_blank=True, max_length=100)


class SellerSubOrderViewSet(ReadOnlyModelViewSet):
    """
    Dashboard for approved sellers to view and manage sub-orders of their products.
    """
    permission_classes = [IsApprovedSeller]
    serializer_class = SellerSubOrderDetailSerializer
    pagination_class = DefaultPagination

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return SubOrder.objects.none()
        seller = self.request.user.seller_profile
        queryset = SubOrder.objects.filter(seller=seller).select_related('order__user').prefetch_related('items__product')
        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)
        return queryset.order_by('-created_at')

    @action(detail=True, methods=['patch'], url_path='status')
    def update_status(self, request, pk=None):
        sub_order = self.get_object()
        serializer = UpdateSubOrderStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_status = serializer.validated_data['status']
        tracking_number = serializer.validated_data.get('tracking_number')

        updated_sub_order = OrderService.update_sub_order_status(
            sub_order=sub_order,
            new_status=new_status,
            tracking_number=tracking_number,
            user=request.user
        )
        return Response(
            {
                "message": f"Sub-order status updated to '{new_status}'",
                "sub_order": SellerSubOrderDetailSerializer(updated_sub_order).data
            },
            status=status.HTTP_200_OK
        )
