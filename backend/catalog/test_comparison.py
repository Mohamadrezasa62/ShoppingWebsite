from django.test import TestCase
from sellers.models import Seller
from .models import Category, Brand, Product, Variant, Offer


class ComparisonTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Phones", slug="phones")
        self.brand = Brand.objects.create(name="Brand", slug="brand")
        self.seller = Seller.objects.create(name="Seller", status="approved")
        self.products = []
        for index in range(5):
            product = Product.objects.create(title=f"Phone {index}", slug=f"phone-{index}", category=self.category, brand=self.brand, status="published", specifications={"screen": str(index), "battery": "large"})
            variant = Variant.objects.create(product=product, sku=f"PHONE-{index}")
            Offer.objects.create(variant=variant, seller=self.seller, price_toman=1000 + index, available_quantity=2, status="active")
            self.products.append(product)

    def get(self, ids):
        return self.client.get("/api/v1/catalog/compare/", {"ids": ids})

    def test_order_specs_and_current_available_price(self):
        first, second = self.products[:2]
        variant = first.variants.get()
        other = Seller.objects.create(name="Other", status="approved")
        cheap = Offer.objects.create(variant=variant, seller=other, price_toman=500, available_quantity=1, reserved_quantity=1, status="active")
        data = self.get(f"{second.pk},{first.pk}").json()
        self.assertEqual([row["id"] for row in data["products"]], [second.pk, first.pk])
        self.assertEqual(data["products"][1]["starting_price_toman"], 1000)
        self.assertEqual(data["specification_keys"], ["screen", "battery"])
        cheap.reserved_quantity = 0
        cheap.save(update_fields=["reserved_quantity"])
        self.assertEqual(self.get(f"{first.pk},{second.pk}").json()["products"][0]["starting_price_toman"], 500)

    def test_invalid_selection_is_bounded(self):
        for ids in ("", "1", "1,1", "1,2,3,4,5", "1,x", "0,2", "9" * 101):
            self.assertEqual(self.get(ids).status_code, 400)

    def test_hidden_or_missing_products_return_no_partial_data(self):
        first, second = self.products[:2]
        first.status = "draft"
        first.save(update_fields=["status"])
        self.assertEqual(self.get(f"{first.pk},{second.pk}").status_code, 404)
        first.status = "published"
        first.save(update_fields=["status"])
        self.brand.is_active = False
        self.brand.save(update_fields=["is_active"])
        self.assertEqual(self.get(f"{first.pk},{second.pk}").status_code, 404)
