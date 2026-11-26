from rest_framework.viewsets import ModelViewSet
from rest_framework.exceptions import PermissionDenied, NotFound
from product.models import Product, ProductImage
from product.serializers import ProductSerializer, ProductImageSerializer
from product.paginations import DefaultPagination
from sellers.permissions import IsApprovedSeller


class SellerProductViewSet(ModelViewSet):
    """
    CRUD API for approved sellers to manage their own products.
    """
    serializer_class = ProductSerializer
    permission_classes = [IsApprovedSeller]
    pagination_class = DefaultPagination

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Product.objects.none()
        return Product.objects.filter(
            seller=self.request.user.seller_profile
        ).select_related('category', 'seller').prefetch_related('images')

    def perform_create(self, serializer):
        serializer.save(seller=self.request.user.seller_profile)


class SellerProductImageViewSet(ModelViewSet):
    """
    Allows approved sellers to upload and delete images for their own products.
    """
    serializer_class = ProductImageSerializer
    permission_classes = [IsApprovedSeller]

    def get_product(self):
        product_pk = self.kwargs.get('product_pk')
        try:
            product = Product.objects.get(pk=product_pk)
        except Product.DoesNotExist:
            raise NotFound("Product does not exist.")

        if product.seller != self.request.user.seller_profile:
            raise PermissionDenied("You can only manage images for your own products.")
        return product

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return ProductImage.objects.none()
        product = self.get_product()
        return ProductImage.objects.filter(product=product)

    def perform_create(self, serializer):
        product = self.get_product()
        serializer.save(product=product)
