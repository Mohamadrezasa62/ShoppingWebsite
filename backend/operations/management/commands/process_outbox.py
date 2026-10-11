from django.core.management.base import BaseCommand
from operations.events import drain


class Command(BaseCommand):
    help = "Process a bounded batch of internal outbox events without a broker"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        limit = options["limit"]
        if not 1 <= limit <= 1000:
            from django.core.management.base import CommandError
            raise CommandError("Limit must be between 1 and 1000")
        self.stdout.write(f"Processed {drain(limit)} events")
