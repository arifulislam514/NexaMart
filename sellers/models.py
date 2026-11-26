from django.db import models
from django.conf import settings
from django.utils.text import slugify
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator


class SellerProfile(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_SUSPENDED = 'suspended'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_SUSPENDED, 'Suspended'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='seller_profile'
    )
    store_name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    description = models.TextField(blank=True, null=True)
    logo = models.ImageField(upload_to="sellers/logos/", blank=True, null=True)
    cover_image = models.ImageField(upload_to="sellers/covers/", blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING
    )
    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=10.00,
        help_text="Platform commission percentage for this seller"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.store_name)
            slug = base_slug
            counter = 1
            while SellerProfile.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def is_approved(self):
        return self.status == self.STATUS_APPROVED

    @property
    def average_rating(self):
        avg = self.reviews.aggregate(avg_rating=models.Avg('rating'))['avg_rating']
        return round(avg, 1) if avg is not None else 0.0

    @property
    def total_reviews(self):
        return self.reviews.count()

    def __str__(self):
        return f"{self.store_name} ({self.get_status_display()})"


class SellerReview(models.Model):
    seller = models.ForeignKey(
        SellerProfile, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='seller_reviews')
    rating = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [['seller', 'user']]
        ordering = ['-created_at']

    def __str__(self):
        return f"Review by {self.user.email} on {self.seller.store_name} ({self.rating}★)"


class SellerCoupon(models.Model):
    TYPE_PERCENT = 'percent'
    TYPE_FIXED = 'fixed'
    TYPE_CHOICES = [
        (TYPE_PERCENT, 'Percentage Discount'),
        (TYPE_FIXED, 'Fixed Amount Discount'),
    ]

    seller = models.ForeignKey(
        SellerProfile, on_delete=models.CASCADE, related_name='coupons')
    code = models.CharField(max_length=50)
    discount_type = models.CharField(
        max_length=10, choices=TYPE_CHOICES, default=TYPE_PERCENT)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    min_purchase = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00)
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField()
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [['seller', 'code']]
        ordering = ['-created_at']

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.valid_to and self.valid_from and self.valid_to <= self.valid_from:
            raise ValidationError("valid_to must be after valid_from")
        if self.discount_type == self.TYPE_PERCENT and self.discount_value > 100:
            raise ValidationError("Percentage discount cannot exceed 100%")

    def is_valid_now(self):
        now = timezone.now()
        return self.active and (self.valid_from <= now <= self.valid_to)

    def calculate_discount(self, amount):
        if amount < self.min_purchase:
            return 0.00
        if self.discount_type == self.TYPE_PERCENT:
            return round(amount * (self.discount_value / 100), 2)
        elif self.discount_type == self.TYPE_FIXED:
            return min(self.discount_value, amount)
        return 0.00

    def __str__(self):
        return f"{self.code} - {self.seller.store_name}"
