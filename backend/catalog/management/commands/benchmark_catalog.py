"""Read-only, in-process profiling. Does not establish HTTP/load-test readiness."""
import json
import math
from pathlib import Path
from statistics import median
from time import perf_counter
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.test import RequestFactory
from django.utils import timezone
from catalog import api, merchandising
from catalog.models import Product, Variant, Offer


class Command(BaseCommand):
    help = "Measure public catalog query counts, response sizes and local durations without logging SQL or customer data"

    def add_arguments(self, parser):
        parser.add_argument("--iterations", type=int, default=20)
        parser.add_argument("--output", required=True)

    def handle(self, *args, **options):
        iterations = options["iterations"]
        if not 1 <= iterations <= 200:
            raise CommandError("Iterations must be between 1 and 200")
        output = Path(options["output"])
        if output.exists():
            raise CommandError("Output already exists; choose a new file")
        factory = RequestFactory()
        product = Product.objects.filter(pk__in=api.visible_offers().values("variant__product_id")).select_related("category").order_by("pk").first()
        if product is None:
            raise CommandError("A visible product is required; use a representative test database")
        cases = [
            ("listing", api.products, {}, {}),
            ("price_sort", api.products, {"sort": "price_asc"}, {}),
            ("search", api.products, {"q": product.title[:12]}, {}),
            ("category", api.products, {"category": product.category.slug}, {}),
            ("suggestions", api.suggestions, {"q": product.title[:12]}, {}),
            ("detail", api.product_detail, {}, {"slug": product.slug}),
            ("related", merchandising.related, {}, {"product_id": product.pk}),
        ]
        results = []
        for name, view, params, kwargs in cases:
            request = factory.get("/", params)
            view(request, **kwargs)  # Warmup is not included in measurements.
            durations, counts, sizes = [], [], []
            for _ in range(iterations):
                count = 0
                def measure(execute, sql, params, many, context):
                    nonlocal count
                    count += 1
                    return execute(sql, params, many, context)
                start = perf_counter()
                with connection.execute_wrapper(measure):
                    response = view(request, **kwargs)
                durations.append((perf_counter() - start) * 1000)
                if response.status_code != 200:
                    raise CommandError(f"Benchmark case {name} failed")
                counts.append(count)
                sizes.append(len(response.content))
            results.append({"case": name, "p50_ms": round(median(durations), 3), "p95_ms": round(sorted(durations)[math.ceil(iterations * .95) - 1], 3), "max_queries": max(counts), "max_response_bytes": max(sizes)})
        report = {"generated_at": timezone.now().isoformat(), "database_vendor": connection.vendor, "iterations": iterations, "products": Product.objects.count(), "variants": Variant.objects.count(), "offers": Offer.objects.count(), "scope": "In-process public views; warmup excluded. No network, concurrent users, Redis, provider, HTTP server or production SLO is measured.", "results": results}
        try:
            with output.open("x", encoding="utf-8") as target:
                json.dump(report, target, ensure_ascii=False, indent=2)
                target.write("\n")
        except OSError as exc:
            raise CommandError("Could not create benchmark output") from exc
        self.stdout.write("Read-only catalog benchmark saved")
