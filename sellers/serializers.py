from rest_framework import serializers
from sellers.models import SellerProfile, SellerReview, SellerCoupon


class SellerProfileSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = SellerProfile
        fields = [
            'id',
            'user',
            'user_email',
            'user_name',
            'store_name',
            'slug',
            'description',
            'logo',
            'cover_image',
            'phone',
            'status',
            'commission_rate',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'user', 'slug', 'status', 'commission_rate', 'created_at', 'updated_at']

    def get_user_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.email


class AdminSellerProfileSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.SerializerMethodField()
    total_products = serializers.SerializerMethodField()

    class Meta:
        model = SellerProfile
        fields = [
            'id',
            'user',
            'user_email',
            'user_name',
            'store_name',
            'slug',
            'description',
            'logo',
            'cover_image',
            'phone',
            'status',
            'commission_rate',
            'total_products',
            'average_rating',
            'total_reviews',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'user', 'slug', 'created_at', 'updated_at']

    def get_user_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.email

    def get_total_products(self, obj):
        return obj.products.count()


class SellerApplicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = SellerProfile
        fields = ['store_name', 'description', 'phone', 'logo', 'cover_image']

    def validate_store_name(self, value):
        if SellerProfile.objects.filter(store_name__iexact=value).exists():
            raise serializers.ValidationError("A store with this name already exists.")
        return value

    def create(self, validated_data):
        user = self.context['request'].user
        if hasattr(user, 'seller_profile'):
            raise serializers.ValidationError("You already have an existing seller profile or application.")
        return SellerProfile.objects.create(
            user=user,
            status=SellerProfile.STATUS_PENDING,
            **validated_data
        )


class PublicStoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = SellerProfile
        fields = ['id', 'store_name', 'slug', 'description', 'logo', 'cover_image', 'phone', 'created_at']


class PublicStoreDetailSerializer(serializers.ModelSerializer):
    total_products = serializers.SerializerMethodField()
    user_email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = SellerProfile
        fields = [
            'id', 'user', 'user_email', 'store_name', 'slug', 'description', 'logo',
            'cover_image', 'phone', 'created_at', 'total_products', 'average_rating', 'total_reviews'
        ]

    def get_total_products(self, obj):
        return obj.products.count()


class SellerReviewSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = SellerReview
        fields = ['id', 'user', 'user_name', 'rating', 'comment', 'created_at', 'updated_at']
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']

    def get_user_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.email

    def validate(self, attrs):
        request = self.context.get('request')
        seller = self.context.get('seller')
        if request and hasattr(request.user, 'seller_profile') and request.user.seller_profile == seller:
            raise serializers.ValidationError("You cannot review your own store.")
        return attrs

    def create(self, validated_data):
        seller = self.context['seller']
        user = self.context['request'].user
        review, created = SellerReview.objects.update_or_create(
            seller=seller,
            user=user,
            defaults=validated_data
        )
        return review


class SellerCouponSerializer(serializers.ModelSerializer):
    is_valid = serializers.BooleanField(source='is_valid_now', read_only=True)

    class Meta:
        model = SellerCoupon
        fields = [
            'id', 'code', 'discount_type', 'discount_value',
            'min_purchase', 'valid_from', 'valid_to', 'active',
            'is_valid', 'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'is_valid']

    def validate_code(self, value):
        return value.strip().upper()

    def validate(self, attrs):
        valid_from = attrs.get('valid_from', self.instance.valid_from if self.instance else None)
        valid_to = attrs.get('valid_to', self.instance.valid_to if self.instance else None)
        discount_type = attrs.get('discount_type', self.instance.discount_type if self.instance else 'percent')
        discount_value = attrs.get('discount_value', self.instance.discount_value if self.instance else 0)

        if valid_from and valid_to and valid_to <= valid_from:
            raise serializers.ValidationError({"valid_to": "valid_to must be after valid_from"})

        if discount_type == 'percent' and discount_value > 100:
            raise serializers.ValidationError({"discount_value": "Percentage discount cannot exceed 100%"})

        return attrs


class CouponValidateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=50)
    store_slug = serializers.CharField(max_length=255, required=False)
    cart_amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0)


class SellerEarningsSerializer(serializers.Serializer):
    total_sub_orders = serializers.IntegerField()
    delivered_sub_orders = serializers.IntegerField()
    pending_sub_orders = serializers.IntegerField()
    canceled_sub_orders = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_commission_paid = serializers.DecimalField(max_digits=12, decimal_places=2)
    net_earnings = serializers.DecimalField(max_digits=12, decimal_places=2)
    pending_earnings = serializers.DecimalField(max_digits=12, decimal_places=2)
