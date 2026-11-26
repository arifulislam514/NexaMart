from django.contrib import admin
from sellers.models import SellerProfile, SellerReview, SellerCoupon


@admin.register(SellerProfile)
class SellerProfileAdmin(admin.ModelAdmin):
    list_display = ('store_name', 'user_email', 'status', 'commission_rate', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('store_name', 'user__email', 'phone')
    readonly_fields = ('slug', 'created_at', 'updated_at')
    actions = ['approve_sellers', 'suspend_sellers']

    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = "User Email"

    @admin.action(description="Approve selected sellers")
    def approve_sellers(self, request, queryset):
        count = queryset.update(status=SellerProfile.STATUS_APPROVED)
        self.message_user(request, f"{count} seller(s) have been successfully approved.")

    @admin.action(description="Suspend selected sellers")
    def suspend_sellers(self, request, queryset):
        count = queryset.update(status=SellerProfile.STATUS_SUSPENDED)
        self.message_user(request, f"{count} seller(s) have been suspended.")


@admin.register(SellerReview)
class SellerReviewAdmin(admin.ModelAdmin):
    list_display = ('seller', 'user_email', 'rating', 'short_comment', 'created_at')
    list_filter = ('rating', 'created_at', 'seller')
    search_fields = ('seller__store_name', 'user__email', 'comment')
    readonly_fields = ('created_at', 'updated_at')

    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = "Customer Email"

    def short_comment(self, obj):
        return obj.comment[:60] + '...' if len(obj.comment) > 60 else obj.comment
    short_comment.short_description = "Comment"


@admin.register(SellerCoupon)
class SellerCouponAdmin(admin.ModelAdmin):
    list_display = ('code', 'seller', 'discount_type', 'discount_value', 'min_purchase', 'active', 'valid_from', 'valid_to')
    list_filter = ('discount_type', 'active', 'seller')
    search_fields = ('code', 'seller__store_name')
