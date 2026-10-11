from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import json
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext
from sellers.models import Seller
from .models import Category, Product, Variant, Offer, ProductMedia
from . import api, merchandising


class CatalogBudgetTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        category = Category.objects.create(name="Phones", slug="phones")
        seller = Seller.objects.create(name="Store", status="approved")
        cls.products = Product.objects.bulk_create([Product(title=f"Phone {n:02d}", slug=f"phone-{n:02d}", category=category, status="published", description="Large detail" * 1000, specifications={"details": "x" * 1000}) for n in range(31)])
        variants = Variant.objects.bulk_create([Variant(product=p, sku=f"SKU-{p.pk}") for p in cls.products])
        Offer.objects.bulk_create([Offer(variant=v, seller=seller, price_toman=100+v.pk, available_quantity=5, status="active") for v in variants])
        # Files are never opened by card responses; this fixture measures metadata.
        ProductMedia.objects.bulk_create([ProductMedia(product=p, image="fixture.png", alt_text="Public image", is_approved=True) for p in cls.products])

    def test_listing_budget_pagination_and_detail_fields_are_not_loaded(self):
        request = RequestFactory().get("/", {"page": 1})
        with CaptureQueriesContext(connection) as queries:
            response = api.products(request)
        data = json.loads(response.content)
        self.assertEqual(len(data["products"]), 24)
        self.assertTrue(data["has_next"])
        self.assertEqual(len(queries), 2)
        self.assertNotIn('"catalog_product"."description"', queries[0]["sql"])
        self.assertNotIn('"catalog_product"."specifications"', queries[0]["sql"])
        self.assertEqual(data["products"][0]["image"]["alt"], "Public image")
        next_page = json.loads(api.products(RequestFactory().get("/", {"page": 2})).content)
        self.assertEqual(len(next_page["products"]), 7)
        self.assertFalse(next_page["has_next"])
        self.assertFalse({p["id"] for p in data["products"]} & {p["id"] for p in next_page["products"]})

    def test_related_limit_is_applied_before_prefetch(self):
        with CaptureQueriesContext(connection) as queries:
            response = merchandising.related(RequestFactory().get("/"), self.products[0].pk)
        self.assertEqual(len(json.loads(response.content)["products"]), 8)
        self.assertEqual(len(queries), 3)
        self.assertIn("LIMIT 8", queries[1]["sql"])
        self.assertNotIn('"catalog_product"."description"', queries[1]["sql"])

    def test_benchmark_is_read_only_bounded_and_refuses_overwrite(self):
        before = (Product.objects.count(), Offer.objects.count(), ProductMedia.objects.count())
        with TemporaryDirectory() as directory:
            output = Path(directory) / "result.json"
            call_command("benchmark_catalog", iterations=1, output=str(output), stdout=StringIO())
            report = json.loads(output.read_text())
            self.assertEqual(report["products"], 31)
            self.assertEqual(len(report["results"]), 7)
            self.assertTrue(all(row["max_queries"] <= 3 for row in report["results"]))
            with self.assertRaises(CommandError):
                call_command("benchmark_catalog", iterations=1, output=str(output))
            with self.assertRaises(CommandError):
                call_command("benchmark_catalog", iterations=0, output=str(Path(directory) / "invalid.json"))
        self.assertEqual(before, (Product.objects.count(), Offer.objects.count(), ProductMedia.objects.count()))
