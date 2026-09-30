from django.core.exceptions import ValidationError
from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=160, unique=True, allow_unicode=True)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="children")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name", "id")

    def clean(self):
        if self.parent_id is None:
            return
        ancestor = self.parent
        visited = set()
        while ancestor is not None:
            if ancestor.pk == self.pk or ancestor.pk in visited:
                raise ValidationError({"parent": "A category cannot be its own ancestor"})
            visited.add(ancestor.pk)
            ancestor = ancestor.parent

    def __str__(self):
        return self.name


class Brand(models.Model):
    name = models.CharField(max_length=160, unique=True)
    slug = models.SlugField(max_length=160, unique=True, allow_unicode=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Product(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    title = models.CharField(max_length=240)
    slug = models.SlugField(max_length=240, unique=True, allow_unicode=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    brand = models.ForeignKey(Brand, null=True, blank=True, on_delete=models.PROTECT, related_name="products")
    description = models.TextField(blank=True)
    specifications = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        if not isinstance(self.specifications, dict):
            raise ValidationError({"specifications": "Specifications must be an object"})

    def __str__(self):
        return self.title


class ProductMedia(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="media")
    image = models.ImageField(upload_to="products/%Y/%m/")
    alt_text = models.CharField(max_length=240)
    position = models.PositiveSmallIntegerField(default=0)
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("position", "id")

    def clean(self):
        if self.image and self.image.size > 5 * 1024 * 1024:
            raise ValidationError({"image": "Image exceeds 5 MB"})

    def __str__(self):
        return f"{self.product}: {self.alt_text}"


class Variant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    sku = models.CharField(max_length=80, unique=True)
    attributes = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    def clean(self):
        if not isinstance(self.attributes, dict):
            raise ValidationError({"attributes": "Attributes must be an object"})

    def __str__(self):
        return self.sku


class Offer(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING_REVIEW = "pending_review", "Pending review"
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        REJECTED = "rejected", "Rejected"

    class Fulfillment(models.TextChoices):
        SELLER = "seller", "Seller"
        PLATFORM = "platform", "Platform"

    variant = models.ForeignKey(Variant, on_delete=models.PROTECT, related_name="offers")
    seller = models.ForeignKey("sellers.Seller", on_delete=models.PROTECT, related_name="offers")
    price_toman = models.PositiveBigIntegerField()
    warranty = models.CharField(max_length=200, blank=True)
    fulfillment = models.CharField(max_length=10, choices=Fulfillment.choices, default=Fulfillment.SELLER)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    available_quantity = models.PositiveIntegerField(default=0)
    reserved_quantity = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["variant", "seller"], name="unique_variant_seller_offer"),
            models.CheckConstraint(condition=models.Q(price_toman__gt=0), name="offer_positive_price"),
            models.CheckConstraint(condition=models.Q(reserved_quantity__lte=models.F("available_quantity")), name="offer_reservations_within_stock"),
        ]

    def clean(self):
        if self.price_toman is not None and self.price_toman <= 0:
            raise ValidationError({"price_toman": "Price must be positive"})
        if self.reserved_quantity > self.available_quantity:
            raise ValidationError({"reserved_quantity": "Reservations exceed stock"})

    def __str__(self):
        return f"{self.seller} / {self.variant}"
