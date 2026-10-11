from django.contrib.auth.models import AbstractUser
from django.db import models

from .managers import UserManager
from .phones import normalize_iran_mobile


class User(AbstractUser):
    username = None
    phone = models.CharField(max_length=16, unique=True)
    session_version = models.PositiveIntegerField(default=0)

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def save(self, *args, **kwargs):
        self.phone = normalize_iran_mobile(self.phone)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.phone


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
