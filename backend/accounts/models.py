from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower

from .managers import UserManager
from .phones import normalize_iran_mobile


class User(AbstractUser):
    username = None
    phone = models.CharField(max_length=16, unique=True, blank=True, null=True)
    session_version = models.PositiveIntegerField(default=0)

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta(AbstractUser.Meta):
        abstract = False
        constraints = [models.UniqueConstraint(Lower("email"), condition=~models.Q(email=""), name="account_email_case_insensitive_unique")]

    def save(self, *args, **kwargs):
        self.phone = normalize_iran_mobile(self.phone) if self.phone else None
        self.email = self.email.strip().lower() if self.email else ""
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if not self.phone and not self.email:
            raise ValidationError("A phone number or email is required.")

    def __str__(self):
        return self.phone or self.email or str(self.pk)


class AccountClosure(models.Model):
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="closure_requests")
    reason = models.CharField(max_length=500)
    status = models.CharField(max_length=12, choices=(("requested", "Requested"), ("withdrawn", "Withdrawn"), ("rejected", "Rejected"), ("completed", "Completed")), default="requested")
    reviewed_by = models.ForeignKey(User, null=True, on_delete=models.PROTECT, related_name="reviewed_closures")
    review_note = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user"], condition=models.Q(status="requested"), name="one_pending_account_closure")]
