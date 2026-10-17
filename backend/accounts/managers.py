from django.contrib.auth.base_user import BaseUserManager

from .phones import normalize_iran_mobile


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, phone=None, password=None, **extra_fields):
        if not phone and not extra_fields.get("email"):
            raise ValueError("A phone number or email is required")
        user = self.model(phone=normalize_iran_mobile(phone) if phone else None, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields["is_staff"] is not True or extra_fields["is_superuser"] is not True:
            raise ValueError("A superuser must have staff and superuser access")
        return self.create_user(phone, password, **extra_fields)
