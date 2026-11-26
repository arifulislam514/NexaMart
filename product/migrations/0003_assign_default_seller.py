from django.db import migrations


def assign_default_seller(apps, schema_editor):
    User = apps.get_model('users', 'User')
    SellerProfile = apps.get_model('sellers', 'SellerProfile')
    Product = apps.get_model('product', 'Product')

    unassigned_products = Product.objects.filter(seller__isnull=True)
    if not unassigned_products.exists():
        return

    admin_user = User.objects.filter(is_superuser=True).first()
    if not admin_user:
        admin_user = User.objects.filter(is_staff=True).first()
    if not admin_user:
        admin_user = User.objects.create(
            email='admin@nexamart.com',
            first_name='NexaMart',
            last_name='Official',
            is_staff=True,
            is_superuser=True
        )

    official_store, _ = SellerProfile.objects.get_or_create(
        user=admin_user,
        defaults={
            'store_name': 'NexaMart Official Store',
            'slug': 'nexamart-official-store',
            'status': 'approved',
            'description': 'Official retail store of NexaMart.',
            'commission_rate': 0.00
        }
    )

    unassigned_products.update(seller=official_store)


def reverse_func(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('product', '0002_product_seller'),
        ('sellers', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(assign_default_seller, reverse_func),
    ]
