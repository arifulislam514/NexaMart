from rest_framework import permissions
from sellers.models import SellerProfile


class IsApprovedSeller(permissions.BasePermission):
    """
    Allows access only to authenticated users who have an approved SellerProfile.
    """
    message = "You must be an approved seller to perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            hasattr(request.user, 'seller_profile') and
            request.user.seller_profile.status == SellerProfile.STATUS_APPROVED
        )
