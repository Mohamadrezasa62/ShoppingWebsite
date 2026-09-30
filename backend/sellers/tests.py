import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from catalog.models import Category, Offer, Product, Variant

from .models import Seller, SellerMembership


class SellerPortalTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user("09123456784")
        self.other = get_user_model().objects.create_user("09123456785")
        category = Category.objects.create(name="Phones", slug="phones")
        product = Product.objects.create(title="Phone", slug="phone", category=category, status=Product.Status.PUBLISHED)
        self.variant = Variant.objects.create(product=product, sku="phone-1", attributes={"color": "black"})

    def post(self, path, body):
        return self.client.post(path, json.dumps(body), content_type="application/json")

    def application(self, name="Store"):
        return {"name": name, "legal_name": "Registered Store Company", "business_identifier": "REG12345678", "contact_phone": "09123456784"}

    def patch(self, path, body):
        return self.client.patch(path, json.dumps(body), content_type="application/json")

    def test_application_needs_signin_then_admin_approval(self):
        self.assertEqual(self.post("/api/v1/seller/applications/", self.application()).status_code, 401)
        self.client.force_login(self.owner)
        response = self.post("/api/v1/seller/applications/", self.application())
        self.assertEqual(response.status_code, 201)
        seller = Seller.objects.get(pk=response.json()["store"]["id"])
        self.assertEqual(seller.status, Seller.Status.APPLIED)
        self.assertEqual(seller.contact_phone, "+989123456784")
        self.assertTrue(SellerMembership.objects.filter(seller=seller, user=self.owner, role=SellerMembership.Role.OWNER).exists())
        self.assertEqual(self.client.get("/api/v1/seller/stores/").json()["stores"][0]["status"], "applied")
        url = f"/api/v1/seller/stores/{seller.pk}/offers/"
        self.assertEqual(self.post(url, {"variant_id": self.variant.pk, "price_toman": 1000, "available_quantity": 2}).status_code, 403)

    def test_approved_owner_can_create_update_and_pause_offer(self):
        seller = Seller.objects.create(name="Approved", status=Seller.Status.APPROVED)
        SellerMembership.objects.create(seller=seller, user=self.owner, role=SellerMembership.Role.OWNER)
        url = f"/api/v1/seller/stores/{seller.pk}/offers/"
        self.client.force_login(self.owner)
        response = self.post(url, {"variant_id": self.variant.pk, "price_toman": 1000, "available_quantity": 3, "warranty": "One year"})
        self.assertEqual(response.status_code, 201)
        offer_id = response.json()["offer"]["id"]
        self.assertEqual(response.json()["offer"]["status"], Offer.Status.ACTIVE)
        self.assertEqual(self.post(url, {"variant_id": self.variant.pk, "price_toman": 1000, "available_quantity": 3}).status_code, 409)
        offer_url = f"{url}{offer_id}/"
        self.assertEqual(self.patch(offer_url, {"price_toman": 1200, "available_quantity": 5, "status": "paused"}).status_code, 200)
        self.assertEqual(Offer.objects.get(pk=offer_id).status, Offer.Status.PAUSED)
        self.assertEqual(self.patch(offer_url, {"status": "active"}).status_code, 200)
        self.assertEqual(self.client.get(url).json()["offers"][0]["price_toman"], 1200)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.patch(offer_url, {"price_toman": 1}).status_code, 404)

    def test_stock_cannot_drop_below_reserved(self):
        seller = Seller.objects.create(name="Approved", status=Seller.Status.APPROVED)
        SellerMembership.objects.create(seller=seller, user=self.owner, role=SellerMembership.Role.OWNER)
        offer = Offer.objects.create(seller=seller, variant=self.variant, price_toman=1000, status=Offer.Status.ACTIVE, available_quantity=4, reserved_quantity=2)
        self.client.force_login(self.owner)
        url = f"/api/v1/seller/stores/{seller.pk}/offers/{offer.pk}/"
        self.assertEqual(self.patch(url, {"available_quantity": 1}).status_code, 400)
        offer.refresh_from_db()
        self.assertEqual(offer.available_quantity, 4)

    def test_rejected_offer_cannot_be_reactivated_by_seller(self):
        seller = Seller.objects.create(name="Approved", status=Seller.Status.APPROVED)
        SellerMembership.objects.create(seller=seller, user=self.owner, role=SellerMembership.Role.OWNER)
        offer = Offer.objects.create(seller=seller, variant=self.variant, price_toman=1000, status=Offer.Status.REJECTED, available_quantity=2)
        self.client.force_login(self.owner)
        response = self.patch(f"/api/v1/seller/stores/{seller.pk}/offers/{offer.pk}/", {"status": "active"})
        self.assertEqual(response.status_code, 409)
        offer.refresh_from_db()
        self.assertEqual(offer.status, Offer.Status.REJECTED)

    def test_variant_lookup_requires_approved_membership(self):
        self.client.force_login(self.owner)
        url = "/api/v1/seller/catalog-variants/"
        self.assertEqual(self.client.get(url, {"q": "phone"}).status_code, 403)
        seller = Seller.objects.create(name="Approved", status=Seller.Status.APPROVED)
        SellerMembership.objects.create(seller=seller, user=self.owner, role=SellerMembership.Role.OWNER)
        self.assertEqual(self.client.get(url, {"q": "phone"}).json()["variants"][0]["sku"], "phone-1")

    def test_changes_require_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post("/api/v1/seller/applications/", json.dumps(self.application()), content_type="application/json").status_code, 403)

    def test_only_approved_owner_can_edit_public_profile(self):
        seller = Seller.objects.create(name="Store", status=Seller.Status.APPROVED)
        SellerMembership.objects.create(seller=seller, user=self.owner, role=SellerMembership.Role.OWNER)
        url = f"/api/v1/seller/stores/{seller.pk}/profile/"
        self.client.force_login(self.owner)
        self.assertEqual(self.patch(url, {"description": "Quality electronics", "contact_phone": "09123456784"}).status_code, 200)
        seller.refresh_from_db()
        self.assertEqual(seller.description, "Quality electronics")
        self.client.force_login(self.other)
        self.assertEqual(self.patch(url, {"description": "Hijack"}).status_code, 404)
