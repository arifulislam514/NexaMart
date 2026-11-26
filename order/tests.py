from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from product.models import Category, Product
from sellers.models import SellerProfile
from order.models import Cart, CartItem, Order, SubOrder
from order.services import OrderService

User = get_user_model()


class MultiSellerOrderTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.category = Category.objects.create(name="Clothing", description="Apparel")

        # Buyer
        self.buyer = User.objects.create_user(
            email="buyer@example.com",
            password="password123",
            first_name="Rahim",
            last_name="Uddin",
            address="Dhaka, Bangladesh",
            phone_number="01800000000"
        )

        # Seller 1 (10% commission)
        self.user1 = User.objects.create_user(email="seller1@example.com", password="password123")
        self.seller1 = SellerProfile.objects.create(
            user=self.user1,
            store_name="Fashion Hub",
            status=SellerProfile.STATUS_APPROVED,
            commission_rate=Decimal("10.00")
        )

        # Seller 2 (15% commission)
        self.user2 = User.objects.create_user(email="seller2@example.com", password="password123")
        self.seller2 = SellerProfile.objects.create(
            user=self.user2,
            store_name="Shoe Planet",
            status=SellerProfile.STATUS_APPROVED,
            commission_rate=Decimal("15.00")
        )

        # Products
        self.tshirt = Product.objects.create(
            name="T-Shirt",
            description="Cotton T-shirt",
            price=Decimal("500.00"),
            stock=20,
            category=self.category,
            seller=self.seller1
        )
        self.jeans = Product.objects.create(
            name="Jeans",
            description="Blue Denim Jeans",
            price=Decimal("1000.00"),
            stock=10,
            category=self.category,
            seller=self.seller1
        )
        self.shoes = Product.objects.create(
            name="Sneakers",
            description="Running shoes",
            price=Decimal("2000.00"),
            stock=5,
            category=self.category,
            seller=self.seller2
        )

    def test_multi_seller_cart_split_into_suborders(self):
        cart = Cart.objects.create(user=self.buyer)
        # 2 T-shirts from Seller 1 = 1000
        CartItem.objects.create(cart=cart, product=self.tshirt, quantity=2)
        # 1 Jeans from Seller 1 = 1000
        CartItem.objects.create(cart=cart, product=self.jeans, quantity=1)
        # 1 Shoes from Seller 2 = 2000
        CartItem.objects.create(cart=cart, product=self.shoes, quantity=1)

        # Total cart = 4000
        order = OrderService.create_order(user_id=self.buyer.id, cart_id=cart.id)

        self.assertEqual(order.total_price, Decimal("4000.00"))
        self.assertEqual(order.status, Order.NOT_PAID)

        # Check SubOrders
        sub_orders = order.sub_orders.all()
        self.assertEqual(sub_orders.count(), 2)

        # SubOrder 1 (Seller 1 - Fashion Hub): Subtotal = 2000, 10% commission = 200, Earning = 1800
        sub1 = order.sub_orders.get(seller=self.seller1)
        self.assertEqual(sub1.subtotal, Decimal("2000.00"))
        self.assertEqual(sub1.commission_rate, Decimal("10.00"))
        self.assertEqual(sub1.commission_amount, Decimal("200.00"))
        self.assertEqual(sub1.seller_earning, Decimal("1800.00"))
        self.assertEqual(sub1.items.count(), 2)

        # SubOrder 2 (Seller 2 - Shoe Planet): Subtotal = 2000, 15% commission = 300, Earning = 1700
        sub2 = order.sub_orders.get(seller=self.seller2)
        self.assertEqual(sub2.subtotal, Decimal("2000.00"))
        self.assertEqual(sub2.commission_rate, Decimal("15.00"))
        self.assertEqual(sub2.commission_amount, Decimal("300.00"))
        self.assertEqual(sub2.seller_earning, Decimal("1700.00"))
        self.assertEqual(sub2.items.count(), 1)

    def test_seller_order_dashboard_scoping_and_status_update(self):
        cart = Cart.objects.create(user=self.buyer)
        CartItem.objects.create(cart=cart, product=self.tshirt, quantity=1) # Seller 1
        CartItem.objects.create(cart=cart, product=self.shoes, quantity=1)  # Seller 2
        order = OrderService.create_order(user_id=self.buyer.id, cart_id=cart.id)

        # Seller 1 views dashboard
        self.client.force_authenticate(user=self.user1)
        res1 = self.client.get('/api/v1/seller/orders/')
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        results1 = res1.data['results'] if isinstance(res1.data, dict) and 'results' in res1.data else res1.data
        self.assertEqual(len(results1), 1)
        sub1_id = results1[0]['id']
        sub1 = SubOrder.objects.get(id=sub1_id)
        self.assertEqual(sub1.seller, self.seller1)

        # Seller 2 views dashboard
        self.client.force_authenticate(user=self.user2)
        res2 = self.client.get('/api/v1/seller/orders/')
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        results2 = res2.data['results'] if isinstance(res2.data, dict) and 'results' in res2.data else res2.data
        self.assertEqual(len(results2), 1)
        sub2_id = results2[0]['id']
        sub2 = SubOrder.objects.get(id=sub2_id)
        self.assertNotEqual(sub1_id, sub2_id)

        # Seller 2 tries to update Seller 1's sub-order -> 404
        bad_update = self.client.patch(f'/api/v1/seller/orders/{sub1_id}/status/', {"status": "shipped"})
        self.assertEqual(bad_update.status_code, status.HTTP_404_NOT_FOUND)

        # Seller 2 updates their own sub-order -> 200
        good_update = self.client.patch(
            f'/api/v1/seller/orders/{sub2_id}/status/',
            {"status": "shipped", "tracking_number": "TRK-998877"}
        )
        self.assertEqual(good_update.status_code, status.HTTP_200_OK)
        sub2.refresh_from_db()
        self.assertEqual(sub2.status, "shipped")
        self.assertEqual(sub2.tracking_number, "TRK-998877")

        # Parent order status should now sync to 'Shipped' (since one suborder is shipped)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.SHIPPED)
