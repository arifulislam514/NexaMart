from django_filters.rest_framework import FilterSet
from product.models import Product


class ProductFilter(FilterSet):
    class Meta:
        model = Product
        fields = {
            'category_id': ['exact'],
            'seller_id': ['exact'],
            'seller__slug': ['exact'],
            'price': ['gt', 'lt']
        }