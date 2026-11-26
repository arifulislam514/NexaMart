import os
import sys
import re
import argparse
import django
from django.core.files import File

# Load environment variables from .env
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE_DIR, '.env'))
except ImportError:
    pass

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'NexaMart.settings')
django.setup()

from product.models import Product, ProductImage

IMAGES_DIR = os.path.join(os.path.dirname(BASE_DIR), "NexaMart_Frontend", "Images")

def upload_images(force=False, product_ids=None):
    if not os.path.exists(IMAGES_DIR):
        print(f"Error: Images directory not found at: {IMAGES_DIR}")
        return

    files = sorted(os.listdir(IMAGES_DIR))
    print(f"Found {len(files)} files in {IMAGES_DIR}")

    pattern = re.compile(r"^(\d+)_(\d+)\.(jpg|jpeg|png)$", re.IGNORECASE)

    # If force or specific products targeted, clear them first
    if force:
        if product_ids:
            print(f"Clearing existing images for products: {product_ids}...")
            ProductImage.objects.filter(product_id__in=product_ids).delete()
        else:
            print("Clearing all existing ProductImage records...")
            ProductImage.objects.all().delete()

    success_count = 0
    skipped_count = 0
    errors = []

    for filename in files:
        match = pattern.match(filename)
        if not match:
            continue

        product_id = int(match.group(1))
        if product_ids and product_id not in product_ids:
            continue

        filepath = os.path.join(IMAGES_DIR, filename)

        try:
            product = Product.objects.get(pk=product_id)
        except Product.DoesNotExist:
            errors.append(f"Product ID {product_id} not found for {filename}")
            continue

        existing = product.images.filter(image__endswith=filename).first()
        if existing and not force:
            skipped_count += 1
            continue

        try:
            with open(filepath, 'rb') as f:
                ProductImage.objects.create(
                    product=product,
                    image=File(f, name=filename)
                )
            success_count += 1
        except Exception as e:
            errors.append(f"Error uploading {filename}: {e}")

    print("\n================ UPLOAD SUMMARY ================")
    print(f"Successfully uploaded: {success_count} images")
    print(f"Skipped: {skipped_count} images")
    print(f"Total ProductImages in DB: {ProductImage.objects.count()}")
    if errors:
        print(f"Errors ({len(errors)}):")
        for err in errors[:5]:
            print(f"  - {err}")
    else:
        print("Done!")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Upload images to NexaMart backend database.")
    parser.add_argument('--force', action='store_true', help="Overwrite/replace existing images.")
    parser.add_argument('--products', nargs='+', type=int, help="Specific product IDs to update.")
    args = parser.parse_args()

    upload_images(force=args.force, product_ids=args.products)
