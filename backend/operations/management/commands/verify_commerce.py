import json
import os
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from operations.invariants import inspect_commerce


class Command(BaseCommand):
    help = "Read-only reservation, order snapshot and cash ledger consistency report; exits nonzero on mismatches"

    def add_arguments(self, parser):
        parser.add_argument("--output", required=True)

    def handle(self, *args, **options):
        output = Path(options["output"])
        if output.exists():
            raise CommandError("Output already exists; choose a new file")
        report = inspect_commerce()
        try:
            descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as target:
                json.dump(report, target, ensure_ascii=False, indent=2)
                target.write("\n")
        except OSError as exc:
            raise CommandError("Could not create consistency report") from exc
        if not report["consistent"]:
            raise CommandError("Commerce mismatches detected; inspect report. No data was changed.")
        self.stdout.write("Commerce snapshot is structurally consistent; no data was changed")
