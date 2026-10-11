from django.conf import settings
from django.db import models


class Seller(models.Model):
    class Status(models.TextChoices):
        APPLIED = "applied", "Applied"
        UNDER_REVIEW = "under_review", "Under review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        SUSPENDED = "suspended", "Suspended"

    name = models.CharField(max_length=200)
    legal_name = models.CharField(max_length=200, blank=True)
    business_identifier = models.CharField(max_length=32, blank=True)
    contact_phone = models.CharField(max_length=13, blank=True)
    description = models.TextField(blank=True)
    commission_bps = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.APPLIED)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="reviewed_sellers"
    )
    review_note = models.TextField(blank=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(commission_bps__lte=10000), name="seller_commission_rate_limit")]

    def __str__(self):
        return self.name


class SellerMembership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        STAFF = "staff", "Staff"

    seller = models.ForeignKey(Seller, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="seller_memberships")
    role = models.CharField(max_length=10, choices=Role.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["seller", "user"], name="unique_seller_membership")]


class ProductProposal(models.Model):
    seller = models.ForeignKey(Seller, on_delete=models.PROTECT, related_name="product_proposals")
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    title = models.CharField(max_length=240)
    category = models.ForeignKey("catalog.Category", on_delete=models.PROTECT)
    description = models.TextField(blank=True)
    sku = models.CharField(max_length=80)
    attributes = models.JSONField(default=dict, blank=True)
    specifications = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=12, choices=(("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")), default="pending")
    product = models.ForeignKey("catalog.Product", null=True, blank=True, on_delete=models.PROTECT)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="reviewed_product_proposals")
    review_note = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)


class SellerReview(models.Model):
    delivery = models.OneToOneField("commerce.OrderDelivery", on_delete=models.PROTECT, related_name="seller_review")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    seller = models.ForeignKey(Seller, on_delete=models.PROTECT, related_name="customer_reviews")
    rating = models.PositiveSmallIntegerField()
    body = models.CharField(max_length=2000)
    status = models.CharField(max_length=12, choices=(("pending", "Pending"), ("published", "Published"), ("rejected", "Rejected")), default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(rating__gte=1, rating__lte=5), name="seller_review_rating_range")]
