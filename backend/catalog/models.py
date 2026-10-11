from uuid import uuid4
from django.core.exceptions import ValidationError
from django.conf import settings
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


class CategoryFacet(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="facets")
    key = models.SlugField(max_length=80, allow_unicode=True)
    label = models.CharField(max_length=120)
    choices = models.JSONField(default=list)
    position = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("position", "id")
        constraints = [models.UniqueConstraint(fields=["category", "key"], name="unique_category_facet_key")]

    def clean(self):
        if "__" in self.key or self.key.lstrip("-").isdecimal() or self.key in models.JSONField().get_lookups():
            raise ValidationError({"key": "Facet keys cannot be query operators, numeric indices or contain consecutive underscores"})
        if not isinstance(self.choices, list) or not self.choices or not all(
            isinstance(value, str) and value.strip() and len(value) <= 100 for value in self.choices
        ) or len(set(self.choices)) != len(self.choices):
            raise ValidationError({"choices": "Choices must be unique, non-empty strings"})

    def __str__(self):
        return f"{self.category}: {self.label}"


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
    inventory_managed = models.BooleanField(default=False)
    inventory_activated_at = models.DateTimeField(null=True, blank=True)

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


class Warehouse(models.Model):
    seller = models.ForeignKey("sellers.Seller", on_delete=models.PROTECT, related_name="warehouses")
    name = models.CharField(max_length=160)
    code = models.SlugField(max_length=80)
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["seller", "code"], name="unique_seller_warehouse_code"), models.UniqueConstraint(fields=["seller"], condition=models.Q(is_default=True), name="one_default_seller_warehouse")]


class StockBalance(models.Model):
    offer = models.ForeignKey(Offer, on_delete=models.PROTECT, related_name="stock_balances")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="balances")
    quantity = models.PositiveIntegerField(default=0)
    reserved_quantity = models.PositiveIntegerField(default=0)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["offer", "warehouse"], name="unique_offer_warehouse_balance"), models.CheckConstraint(condition=models.Q(reserved_quantity__lte=models.F("quantity")), name="warehouse_reservations_within_stock")]


class StockReservation(models.Model):
    order_line = models.ForeignKey("commerce.OrderLine", on_delete=models.PROTECT, related_name="stock_reservations")
    balance = models.ForeignKey(StockBalance, on_delete=models.PROTECT, related_name="reservations")
    quantity = models.PositiveIntegerField()
    restocked_quantity = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=12, choices=(("reserved", "Reserved"), ("consumed", "Consumed"), ("released", "Released")), default="reserved")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["order_line", "balance"], name="unique_line_stock_reservation"), models.CheckConstraint(condition=models.Q(quantity__gt=0, restocked_quantity__lte=models.F("quantity")), name="valid_stock_reservation_quantity")]


class StockMovement(models.Model):
    balance = models.ForeignKey(StockBalance, on_delete=models.PROTECT, related_name="movements")
    order_line = models.ForeignKey("commerce.OrderLine", null=True, on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    kind = models.CharField(max_length=24)
    quantity_delta = models.IntegerField(default=0)
    reserved_delta = models.IntegerField(default=0)
    event_key = models.CharField(max_length=200, unique=True)
    reason = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Stock movement history is immutable")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Stock movement history is immutable")


class StockImportReceipt(models.Model):
    seller = models.ForeignKey("sellers.Seller", on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    request_key = models.UUIDField()
    digest = models.CharField(max_length=64)
    updated_count = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["seller", "request_key"], name="unique_seller_inventory_import")]


class WishlistItem(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wishlist_items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="wishlist_items")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "product"], name="unique_wishlist_product")]


class ProductReview(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PUBLISHED = "published", "Published"
        REJECTED = "rejected", "Rejected"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="product_reviews")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="reviews")
    rating = models.PositiveSmallIntegerField()
    title = models.CharField(max_length=160)
    body = models.TextField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    verified_purchase = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "product"], name="unique_user_product_review"),
            models.CheckConstraint(condition=models.Q(rating__gte=1, rating__lte=5), name="review_rating_one_to_five"),
        ]


class ProductQuestion(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="questions")
    body = models.CharField(max_length=2000)
    answer = models.CharField(max_length=4000, blank=True)
    status = models.CharField(max_length=12, choices=ProductReview.Status.choices, default="pending")
    answered_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="answered_questions")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class ReviewMedia(models.Model):
    review = models.ForeignKey(ProductReview, on_delete=models.PROTECT, related_name="media")
    image = models.ImageField(upload_to="review-images/%Y/%m/")
    alt_text = models.CharField(max_length=240)
    status = models.CharField(max_length=12, choices=(("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected"), ("withdrawn", "Withdrawn")), default="pending")
    request_key = models.UUIDField()
    digest = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["review", "request_key"], name="unique_review_image_request")]


class ProductAlert(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="product_alerts")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="alerts")
    kind = models.CharField(max_length=20, choices=(("price_drop", "Price drop"), ("back_in_stock", "Back in stock")))
    target_price_toman = models.PositiveBigIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    generation = models.UUIDField(default=uuid4)
    notified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "product", "kind"], name="unique_user_product_alert"),
            models.CheckConstraint(condition=(models.Q(kind="back_in_stock", target_price_toman__isnull=True) | models.Q(kind="price_drop", target_price_toman__isnull=False, target_price_toman__gt=0)), name="valid_product_alert_target"),
        ]
        indexes = [models.Index(fields=["is_active", "id"])]


class ProductCollection(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, allow_unicode=True)
    description = models.TextField(blank=True)
    products = models.ManyToManyField(Product, blank=True, related_name="collections")
    is_published = models.BooleanField(default=False)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        if self.starts_at and self.ends_at and self.starts_at >= self.ends_at:
            raise ValidationError("Collection end must be after start")


class FollowSubscription(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="following")
    brand = models.ForeignKey(Brand, null=True, on_delete=models.PROTECT)
    seller = models.ForeignKey("sellers.Seller", null=True, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=(models.Q(brand__isnull=False, seller__isnull=True) | models.Q(brand__isnull=True, seller__isnull=False)), name="follow_exactly_one_target"),
            models.UniqueConstraint(fields=["user", "brand"], name="unique_user_followed_brand"),
            models.UniqueConstraint(fields=["user", "seller"], name="unique_user_followed_seller"),
        ]


class BrowsingPreference(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="browsing_preference")
    enabled = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)


class RecentProductView(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="recent_product_views")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    viewed_at = models.DateTimeField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "product"], name="unique_recent_user_product")]
        indexes = [models.Index(fields=["user", "-viewed_at", "-id"]), models.Index(fields=["viewed_at"])]


class CatalogImportJob(models.Model):
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    idempotency_key = models.UUIDField()
    source_digest = models.CharField(max_length=64)
    mode = models.CharField(max_length=8, choices=(("create", "Create drafts"), ("update", "Update content")), default="create")
    rows = models.JSONField()
    row_count = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=12, choices=(("queued", "Queued"), ("succeeded", "Succeeded"), ("failed", "Failed")), default="queued")
    attempt = models.PositiveSmallIntegerField(default=1)
    last_event = models.ForeignKey("operations.OutboxEvent", null=True, on_delete=models.PROTECT)
    error = models.JSONField(default=dict)
    product_ids = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["requested_by", "idempotency_key"], name="unique_catalog_import_request")]
