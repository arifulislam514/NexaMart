from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from product.models import Category, Product
from sellers.models import SellerProfile

User = get_user_model()


class SellerProductTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.category = Category.objects.create(name="Electronics", description="Gadgets")

        # Seller 1 (Approved)
        self.user1 = User.objects.create_user(email="seller1@example.com", password="password123")
        self.seller1 = SellerProfile.objects.create(
            user=self.user1,
            store_name="Seller One Store",
            status=SellerProfile.STATUS_APPROVED
        )

        # Seller 2 (Approved)
        self.user2 = User.objects.create_user(email="seller2@example.com", password="password123")
        self.seller2 = SellerProfile.objects.create(
            user=self.user2,
            store_name="Seller Two Store",
            status=SellerProfile.STATUS_APPROVED
        )

        # Pending Seller
        self.pending_user = User.objects.create_user(email="pending@example.com", password="password123")
        self.pending_seller = SellerProfile.objects.create(
            user=self.pending_user,
            store_name="Pending Store",
            status=SellerProfile.STATUS_PENDING
        )

    def test_approved_seller_can_create_product(self):
        self.client.force_authenticate(user=self.user1)
        payload = {
            "name": "Smart Watch",
            "description": "Fitness tracking smartwatch",
            "price": 1500.00,
            "stock": 10,
            "category": self.category.id
        }
        response = self.client.post('/api/v1/seller/products/', payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        product = Product.objects.get(name="Smart Watch")
        self.assertEqual(product.seller, self.seller1)
        self.assertEqual(response.data['seller']['id'], self.seller1.id)

    def test_pending_seller_cannot_create_product(self):
        self.client.force_authenticate(user=self.pending_user)
        payload = {
            "name": "Unapproved Watch",
            "description": "Description",
            "price": 1000.00,
            "stock": 5,
            "category": self.category.id
        }
        response = self.client.post('/api/v1/seller/products/', payload)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_seller_catalog_isolation(self):
        # Product 1 belongs to Seller 1
        p1 = Product.objects.create(
            name="Product One", description="Desc 1", price=100.00,
            stock=5, category=self.category, seller=self.seller1
        )
        # Product 2 belongs to Seller 2
        p2 = Product.objects.create(
            name="Product Two", description="Desc 2", price=200.00,
            stock=10, category=self.category, seller=self.seller2
        )

        # Seller 1 views their products
        self.client.force_authenticate(user=self.user1)
        response = self.client.get('/api/v1/seller/products/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Results should contain Product 1, but NOT Product 2
        results = response.data['results'] if isinstance(response.data, dict) and 'results' in response.data else response.data
        product_ids = [p['id'] for p in results]
        self.assertIn(p1.id, product_ids)
        self.assertNotIn(p2.id, product_ids)

        # Seller 1 tries to edit Seller 2's product -> 404
        update_res = self.client.patch(f'/api/v1/seller/products/{p2.id}/', {"price": 250.00})
        self.assertEqual(update_res.status_code, status.HTTP_404_NOT_FOUND)

        # Seller 1 edits their own product -> 200
        edit_res = self.client.patch(f'/api/v1/seller/products/{p1.id}/', {"price": 120.00})
        self.assertEqual(edit_res.status_code, status.HTTP_200_OK)
        p1.refresh_from_db()
        self.assertEqual(p1.price, 120.00)
