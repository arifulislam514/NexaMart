from decimal import Decimal
from order.models import Cart, CartItem, OrderItem, Order, SubOrder
from product.models import Product
from sellers.models import SellerProfile
from django.db import transaction, models
from rest_framework.exceptions import PermissionDenied, ValidationError


class OrderService:
    @staticmethod
    def create_order(user_id, cart_id):
        with transaction.atomic():
            try:
                cart = Cart.objects.get(pk=cart_id)
            except Cart.DoesNotExist:
                raise ValidationError({"detail": "No cart found with this id"})

            cart_items = list(cart.items.select_related('product__seller').all())
            if not cart_items:
                raise ValidationError({"detail": "Cart is empty"})

            # Check stock availability for all items with row-level locking
            products_to_update = []
            for item in cart_items:
                product = Product.objects.select_for_update().get(pk=item.product_id)
                if product.stock < item.quantity:
                    raise ValidationError(
                        {"detail": f"Insufficient stock for '{product.name}'. Available: {product.stock}, requested: {item.quantity}"}
                    )
                product.stock -= item.quantity
                products_to_update.append(product)

            # Deduct stock for all items
            for p in products_to_update:
                p.save(update_fields=['stock'])

            # Group items by seller
            default_seller = None
            seller_items_map = {}
            for item in cart_items:
                seller = item.product.seller
                if not seller:
                    if not default_seller:
                        default_seller = SellerProfile.objects.filter(status=SellerProfile.STATUS_APPROVED).first()
                    seller = default_seller

                if not seller:
                    raise ValidationError({"detail": f"Product '{item.product.name}' has no assigned seller."})

                if seller not in seller_items_map:
                    seller_items_map[seller] = []
                seller_items_map[seller].append(item)

            total_price = sum([item.product.price * item.quantity for item in cart_items])
            order = Order.objects.create(user_id=user_id, total_price=total_price)

            # Create SubOrder for each seller and bulk create respective OrderItems
            all_order_items = []
            for seller, items in seller_items_map.items():
                subtotal = sum([item.product.price * item.quantity for item in items])
                comm_rate = getattr(seller, 'commission_rate', Decimal('10.00'))
                comm_amount = round(subtotal * (comm_rate / Decimal('100.00')), 2)
                seller_earning = subtotal - comm_amount

                sub_order = SubOrder.objects.create(
                    order=order,
                    seller=seller,
                    status=SubOrder.STATUS_PENDING,
                    subtotal=subtotal,
                    commission_rate=comm_rate,
                    commission_amount=comm_amount,
                    seller_earning=seller_earning
                )

                for item in items:
                    all_order_items.append(
                        OrderItem(
                            order=order,
                            sub_order=sub_order,
                            product=item.product,
                            price=item.product.price,
                            quantity=item.quantity,
                            total_price=item.product.price * item.quantity
                        )
                    )

            OrderItem.objects.bulk_create(all_order_items)
            cart.delete()
            return order

    @staticmethod
    def cancel_order(order, user):
        if user.is_staff:
            return OrderService._execute_cancel(order)

        if order.user != user:
            raise PermissionDenied(
                {"detail": "You can only cancel your own order"})

        if order.status == Order.DELIVERED:
            raise ValidationError({"detail": "You cannot cancel an order that has already been delivered"})

        if order.status == Order.CANCELED:
            raise ValidationError({"detail": "Order is already canceled"})

        return OrderService._execute_cancel(order)

    @staticmethod
    def _execute_cancel(order):
        with transaction.atomic():
            if order.status != Order.CANCELED:
                # Restore stock for each item in the canceled order
                for item in order.items.select_related('product').all():
                    Product.objects.filter(pk=item.product_id).update(
                        stock=models.F('stock') + item.quantity
                    )
                order.status = Order.CANCELED
                order.save(update_fields=['status'])
                order.sub_orders.update(status=SubOrder.STATUS_CANCELED)
            return order

    @staticmethod
    def update_order_status(order, new_status):
        with transaction.atomic():
            old_status = order.status
            if old_status == new_status:
                return order

            # If moving to CANCELED, restore stock
            if new_status == Order.CANCELED and old_status != Order.CANCELED:
                for item in order.items.select_related('product').all():
                    Product.objects.filter(pk=item.product_id).update(
                        stock=models.F('stock') + item.quantity
                    )
                order.sub_orders.update(status=SubOrder.STATUS_CANCELED)

            # If moving from CANCELED back to an active status, re-deduct stock
            elif old_status == Order.CANCELED and new_status != Order.CANCELED:
                for item in order.items.select_related('product').all():
                    product = Product.objects.select_for_update().get(pk=item.product_id)
                    if product.stock < item.quantity:
                        raise ValidationError(
                            {"detail": f"Cannot un-cancel order: Insufficient stock for '{product.name}'. Available: {product.stock}, required: {item.quantity}"}
                        )
                    product.stock -= item.quantity
                    product.save(update_fields=['stock'])

            order.status = new_status
            order.save(update_fields=['status'])
            return order

    @staticmethod
    def update_sub_order_status(sub_order, new_status, tracking_number=None, user=None):
        with transaction.atomic():
            if user and not user.is_staff:
                if not hasattr(user, 'seller_profile') or sub_order.seller != user.seller_profile:
                    raise PermissionDenied({"detail": "You can only update your own sub-orders."})

            old_status = sub_order.status
            if old_status == new_status and tracking_number is None:
                return sub_order

            # If this sub-order is canceled, restore stock for this sub-order's items
            if new_status == SubOrder.STATUS_CANCELED and old_status != SubOrder.STATUS_CANCELED:
                for item in sub_order.items.select_related('product').all():
                    Product.objects.filter(pk=item.product_id).update(
                        stock=models.F('stock') + item.quantity
                    )

            sub_order.status = new_status
            if tracking_number is not None:
                sub_order.tracking_number = tracking_number
            sub_order.save()

            # Synchronize parent order status
            sub_order.order.sync_status_from_sub_orders()
            return sub_order
