from django.contrib.auth.models import AbstractUser
from django.db import models

from .managers import UserManager
from .phones import normalize_iran_mobile


class User(AbstractUser):
    username = None
    phone = models.CharField(max_length=16, unique=True)

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def save(self, *args, **kwargs):
        self.phone = normalize_iran_mobile(self.phone)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.phone
