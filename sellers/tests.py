from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from sellers.models import SellerProfile

User = get_user_model()


class SellerApplicationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="seller_applicant@example.com",
            password="testpassword123",
            first_name="Rahim",
            last_name="Uddin"
        )
        self.client.force_authenticate(user=self.user)

    def test_apply_seller_success(self):
        payload = {
            "store_name": "Rahim Gadget Store",
            "description": "Authorized retailer for electronics.",
            "phone": "01700000000"
        }
        response = self.client.post('/api/v1/sellers/apply/', payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(SellerProfile.objects.filter(store_name="Rahim Gadget Store").exists())
        profile = SellerProfile.objects.get(store_name="Rahim Gadget Store")
        self.assertEqual(profile.status, SellerProfile.STATUS_PENDING)
        self.assertEqual(profile.slug, "rahim-gadget-store")
        self.assertFalse(profile.is_approved)

    def test_duplicate_seller_application_fails(self):
        SellerProfile.objects.create(
            user=self.user,
            store_name="Rahim Gadget Store",
            status=SellerProfile.STATUS_PENDING
        )
        payload = {
            "store_name": "Rahim Second Store",
            "description": "Another store"
        }
        response = self.client.post('/api/v1/sellers/apply/', payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_duplicate_store_name_validation(self):
        other_user = User.objects.create_user(
            email="other@example.com",
            password="testpassword123"
        )
        SellerProfile.objects.create(
            user=other_user,
            store_name="Unique Tech",
            status=SellerProfile.STATUS_APPROVED
        )
        payload = {
            "store_name": "Unique Tech",
            "description": "Duplicate name test"
        }
        response = self.client.post('/api/v1/sellers/apply/', payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_seller_profile_me_endpoint(self):
        profile = SellerProfile.objects.create(
            user=self.user,
            store_name="Rahim Tech",
            status=SellerProfile.STATUS_APPROVED
        )
        response = self.client.get('/api/v1/seller/profile/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['store_name'], "Rahim Tech")
        self.assertEqual(response.data['status'], "approved")

        # Test PATCH update
        update_res = self.client.patch('/api/v1/seller/profile/', {"description": "Updated description"})
        self.assertEqual(update_res.status_code, status.HTTP_200_OK)
        profile.refresh_from_db()
        self.assertEqual(profile.description, "Updated description")

    def test_seller_earnings_summary(self):
        from decimal import Decimal
        from order.models import Order, SubOrder

        profile = SellerProfile.objects.create(
            user=self.user,
            store_name="Gadget Lab",
            status=SellerProfile.STATUS_APPROVED
        )
        order = Order.objects.create(user=self.user, total_price=Decimal("2000.00"))

        # Delivered SubOrder
        SubOrder.objects.create(
            order=order,
            seller=profile,
            status=SubOrder.STATUS_DELIVERED,
            subtotal=Decimal("1000.00"),
            commission_rate=Decimal("10.00"),
            commission_amount=Decimal("100.00"),
            seller_earning=Decimal("900.00")
        )

        # Pending SubOrder
        SubOrder.objects.create(
            order=order,
            seller=profile,
            status=SubOrder.STATUS_PENDING,
            subtotal=Decimal("500.00"),
            commission_rate=Decimal("10.00"),
            commission_amount=Decimal("50.00"),
            seller_earning=Decimal("450.00")
        )

        response = self.client.get('/api/v1/seller/earnings/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['delivered_sub_orders'], 1)
        self.assertEqual(response.data['pending_sub_orders'], 1)
        self.assertEqual(Decimal(str(response.data['total_revenue'])), Decimal("1000.00"))
        self.assertEqual(Decimal(str(response.data['net_earnings'])), Decimal("900.00"))
        self.assertEqual(Decimal(str(response.data['pending_earnings'])), Decimal("450.00"))

    def test_public_store_endpoints(self):
        profile = SellerProfile.objects.create(
            user=self.user,
            store_name="Tech World",
            status=SellerProfile.STATUS_APPROVED
        )
        # Public store profile
        res = self.client.get(f'/api/v1/stores/{profile.slug}/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['store_name'], "Tech World")

        # Public store products
        res_prod = self.client.get(f'/api/v1/stores/{profile.slug}/products/')
        self.assertEqual(res_prod.status_code, status.HTTP_200_OK)

    def test_seller_reviews_and_average_rating(self):
        from sellers.models import SellerReview
        store_owner = User.objects.create_user(email="storeowner@example.com", password="password123")
        store = SellerProfile.objects.create(
            user=store_owner,
            store_name="Great Electronics",
            status=SellerProfile.STATUS_APPROVED
        )

        # Buyer 1 leaves review
        buyer1 = User.objects.create_user(email="buyer1@example.com", password="password123")
        self.client.force_authenticate(user=buyer1)
        res1 = self.client.post(f'/api/v1/stores/{store.slug}/reviews/', {
            "rating": 5,
            "comment": "Fast delivery and authentic products!"
        })
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)

        # Buyer 2 leaves review
        buyer2 = User.objects.create_user(email="buyer2@example.com", password="password123")
        self.client.force_authenticate(user=buyer2)
        res2 = self.client.post(f'/api/v1/stores/{store.slug}/reviews/', {
            "rating": 4,
            "comment": "Good customer support."
        })
        self.assertEqual(res2.status_code, status.HTTP_201_CREATED)

        # Owner cannot review own store
        self.client.force_authenticate(user=store_owner)
        res_owner = self.client.post(f'/api/v1/stores/{store.slug}/reviews/', {
            "rating": 5,
            "comment": "Self review attempt"
        })
        self.assertEqual(res_owner.status_code, status.HTTP_400_BAD_REQUEST)

        # Verify average rating on public store profile
        store_res = self.client.get(f'/api/v1/stores/{store.slug}/')
        self.assertEqual(store_res.status_code, status.HTTP_200_OK)
        self.assertEqual(store_res.data['total_reviews'], 2)
        self.assertEqual(float(store_res.data['average_rating']), 4.5)

    def test_seller_coupon_crud_and_validation(self):
        from django.utils import timezone
        from datetime import timedelta
        from decimal import Decimal
        from sellers.models import SellerCoupon

        seller_user = User.objects.create_user(email="coupon_seller@example.com", password="password123")
        seller = SellerProfile.objects.create(
            user=seller_user,
            store_name="Gadget Zone",
            status=SellerProfile.STATUS_APPROVED
        )

        # Seller creates coupon
        self.client.force_authenticate(user=seller_user)
        now = timezone.now()
        payload = {
            "code": "GZ20",
            "discount_type": "percent",
            "discount_value": "20.00",
            "min_purchase": "500.00",
            "valid_from": (now - timedelta(days=1)).isoformat(),
            "valid_to": (now + timedelta(days=7)).isoformat(),
            "active": True
        }
        create_res = self.client.post('/api/v1/seller/coupons/', payload)
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_res.data['code'], "GZ20")

        # Customer validates coupon with amount >= min_purchase
        customer = User.objects.create_user(email="cust@example.com", password="password123")
        self.client.force_authenticate(user=customer)
        val_res = self.client.post('/api/v1/coupons/validate/', {
            "code": "GZ20",
            "store_slug": "gadget-zone",
            "cart_amount": "1000.00"
        })
        self.assertEqual(val_res.status_code, status.HTTP_200_OK)
        self.assertTrue(val_res.data['valid'])
        self.assertEqual(Decimal(str(val_res.data['discount_amount'])), Decimal("200.00"))
        self.assertEqual(Decimal(str(val_res.data['final_amount'])), Decimal("800.00"))

        # Customer validates with cart_amount < min_purchase -> 400
        fail_res = self.client.post('/api/v1/coupons/validate/', {
            "code": "GZ20",
            "store_slug": "gadget-zone",
            "cart_amount": "300.00"
        })
        self.assertEqual(fail_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(fail_res.data['valid'])
