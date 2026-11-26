from django.contrib import admin
from sellers.models import SellerProfile


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
