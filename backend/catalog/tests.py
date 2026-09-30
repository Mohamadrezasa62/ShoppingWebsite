from django.test import TestCase

from sellers.models import Seller

from .models import Brand, Category, Offer, Product, Variant


class PublicCatalogTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Mobile", slug="mobile")
        self.brand = Brand.objects.create(name="Example", slug="example")
        self.product = Product.objects.create(
            title="Example phone", slug="example-phone", category=self.category,
            brand=self.brand, status=Product.Status.PUBLISHED,
            specifications={"screen": "large"},
        )
        self.variant = Variant.objects.create(product=self.product, sku="phone-black", attributes={"color": "black"})
        self.seller_a = Seller.objects.create(name="Seller A", status=Seller.Status.APPROVED)
        self.seller_b = Seller.objects.create(name="Seller B", status=Seller.Status.APPROVED)
        self.offer_a = Offer.objects.create(
            variant=self.variant, seller=self.seller_a, price_toman=100000,
            status=Offer.Status.ACTIVE, available_quantity=5, reserved_quantity=2,
        )
        self.offer_b = Offer.objects.create(
            variant=self.variant, seller=self.seller_b, price_toman=90000,
            status=Offer.Status.ACTIVE, available_quantity=2,
        )

    def test_search_and_detail_show_two_seller_offers_in_price_order(self):
        response = self.client.get("/api/v1/catalog/products/", {"q": "phone", "category": "mobile"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["products"][0]["starting_price_toman"], 90000)
        detail = self.client.get("/api/v1/catalog/products/example-phone/")
        self.assertEqual([row["seller"]["name"] for row in detail.json()["product"]["offers"]], ["Seller B", "Seller A"])
        self.assertEqual(detail.json()["product"]["offers"][1]["available_quantity"], 3)

    def test_unavailable_and_unapproved_offers_are_hidden(self):
        self.offer_b.reserved_quantity = 2
        self.offer_b.save()
        self.seller_a.status = Seller.Status.SUSPENDED
        self.seller_a.save()
        self.assertEqual(self.client.get("/api/v1/catalog/products/").json()["products"], [])
        self.assertEqual(self.client.get("/api/v1/catalog/products/example-phone/").status_code, 404)

    def test_draft_product_is_hidden(self):
        self.product.status = Product.Status.DRAFT
        self.product.save()
        self.assertEqual(self.client.get("/api/v1/catalog/products/").json()["products"], [])

    def test_inactive_category_is_hidden(self):
        self.category.is_active = False
        self.category.save()
        self.assertEqual(self.client.get("/api/v1/catalog/categories/").json()["categories"], [])
        self.assertEqual(self.client.get("/api/v1/catalog/products/").json()["products"], [])
