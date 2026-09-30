from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

from accounts.roles import STAFF_ROLES


class Command(BaseCommand):
    help = "Create the marketplace staff role groups without creating accounts"

    def handle(self, *args, **options):
        for name in STAFF_ROLES:
            Group.objects.get_or_create(name=name)
        self.stdout.write(self.style.SUCCESS("Staff role groups are ready"))
