import json
import os
from pathlib import Path
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.test import Client
from commerce.models import Address


class Command(BaseCommand):
    help = "Create development-only, short-lived browser fixture sessions in a private file"

    def add_arguments(self, parser):
        parser.add_argument("--output", required=True)

    def handle(self, *args, **options):
        if not settings.DEBUG or os.environ.get("E2E_FIXTURES") != "1":
            raise CommandError("Requires DJANGO_DEBUG=1 and E2E_FIXTURES=1 in a disposable test database")
        target = Path(options["output"])
        if not target.is_absolute() or target.resolve().is_relative_to(settings.BASE_DIR.parent):
            raise CommandError("Session fixture output must be an absolute path outside the repository")
        call_command("seed_demo")
        user, _ = get_user_model().objects.get_or_create(phone="+989123456831")
        admin, _ = get_user_model().objects.get_or_create(phone="+989123456832", defaults={"is_staff": True, "is_superuser": True})
        if not admin.is_superuser:
            raise CommandError("Fixture identity collides with a non-admin user")
        Address.objects.get_or_create(user=user, postal_code="1234567890", defaults={"full_name": "خریدار آزمون", "phone": user.phone, "province": "تهران", "city": "تهران", "street": "نشانی آزمون"})
        result = {}
        for name, account in (("buyer", user), ("admin", admin)):
            client = Client()
            client.force_login(account)
            session = client.session
            session.set_expiry(600)
            session.save()
            result[name] = client.cookies[settings.SESSION_COOKIE_NAME].value
        # Exclusively create a private credential file; never log session values.
        descriptor = os.open(options["output"], os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as output:
            json.dump(result, output)
        self.stdout.write("Short-lived browser fixture file created")
