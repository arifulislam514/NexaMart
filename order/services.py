from order.models import Cart, CartItem, OrderItem, Order
from product.models import Product
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

            cart_items = list(cart.items.select_related('product').all())
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

            total_price = sum([item.product.price *
                               item.quantity for item in cart_items])

            order = Order.objects.create(
                user_id=user_id, total_price=total_price)

            order_items = [
                OrderItem(
                    order=order,
                    product=item.product,
                    price=item.product.price,
                    quantity=item.quantity,
                    total_price=item.product.price * item.quantity
                )
                for item in cart_items
            ]
            OrderItem.objects.bulk_create(order_items)

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

