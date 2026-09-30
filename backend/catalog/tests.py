from io import BytesIO
from tempfile import TemporaryDirectory

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image

from sellers.models import Seller

from .models import Brand, Category, Offer, Product, ProductMedia, Variant


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

    def test_brand_and_price_filters_use_eligible_offer_price(self):
        self.assertEqual(self.client.get("/api/v1/catalog/brands/").json()["brands"], [{"name": "Example", "slug": "example"}])
        result = self.client.get("/api/v1/catalog/products/", {"brand": "example", "min_price": "95000"}).json()
        self.assertEqual(result["products"][0]["starting_price_toman"], 100000)
        self.assertEqual(self.client.get("/api/v1/catalog/products/", {"max_price": "80000"}).json()["products"], [])
        self.assertEqual(self.client.get("/api/v1/catalog/products/", {"min_price": "100", "max_price": "10"}).status_code, 400)
        self.brand.is_active = False
        self.brand.save()
        self.assertEqual(self.client.get("/api/v1/catalog/brands/").json()["brands"], [])
        self.assertEqual(self.client.get("/api/v1/catalog/products/").json()["products"], [])

    def test_only_approved_images_are_public(self):
        image_bytes = BytesIO()
        Image.new("RGB", (8, 8), "red").save(image_bytes, format="PNG")
        with TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            approved = ProductMedia.objects.create(product=self.product, image=SimpleUploadedFile("approved.png", image_bytes.getvalue(), content_type="image/png"), alt_text="Front view", is_approved=True)
            pending = ProductMedia.objects.create(product=self.product, image=SimpleUploadedFile("pending.png", image_bytes.getvalue(), content_type="image/png"), alt_text="Pending view")
            listing = self.client.get("/api/v1/catalog/products/").json()["products"][0]
            self.assertEqual(listing["image"]["alt"], "Front view")
            detail = self.client.get("/api/v1/catalog/products/example-phone/").json()["product"]
            self.assertEqual(len(detail["images"]), 1)
            self.assertEqual(detail["images"][0]["url"], f"/api/v1/catalog/media/{approved.pk}/")
            image_response = self.client.get(detail["images"][0]["url"])
            self.assertEqual(image_response.status_code, 200)
            self.assertEqual(b"".join(image_response.streaming_content), image_bytes.getvalue())
            self.assertEqual(self.client.get(f"/api/v1/catalog/media/{pending.pk}/").status_code, 404)
            self.assertEqual(self.client.get(pending.image.url).status_code, 404)
