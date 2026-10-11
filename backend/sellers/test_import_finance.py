from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from catalog.models import Offer
from .models import Seller, SellerMembership
from .tests import SellerPortalTests


class SellerImportTests(TestCase):
    def setUp(self):
        SellerPortalTests.setUp(self)
        self.seller = Seller.objects.create(name="Store", status="approved")
        SellerMembership.objects.create(user=self.owner, seller=self.seller, role="owner")
        self.offer = Offer.objects.create(seller=self.seller, variant=self.variant, price_toman=1000, available_quantity=3, reserved_quantity=1, status="active")
        self.client.force_login(self.owner)
        self.path = f"/api/v1/seller/stores/{self.seller.pk}/offers-csv/"

    def upload(self, text):
        return self.client.post(self.path, {"file": SimpleUploadedFile("offers.csv", text.encode(), content_type="text/csv")})

    def test_import_is_atomic_and_does_not_reduce_reserved_stock(self):
        header = "sku,price_toman,available_quantity,status,warranty\n"
        response = self.upload(header + "phone-1,2000,4,active,One year\nUNKNOWN,3000,2,active,\n")
        self.assertEqual(response.status_code, 400)
        self.offer.refresh_from_db()
        self.assertEqual(self.offer.price_toman, 1000)
        self.assertEqual(self.upload(header + "phone-1,2000,0,active,\n").status_code, 400)
        self.assertEqual(self.upload(header + "phone-1,2000,4,active,One year\n").status_code, 200)
        self.offer.refresh_from_db()
        self.assertEqual(self.offer.price_toman, 2000)

    def test_export_neutralizes_spreadsheet_formulas_and_finance_is_private(self):
        self.offer.warranty = "=HYPERLINK(\"https://example.invalid\")"
        self.offer.save()
        self.assertIn("'=HYPERLINK", self.client.get(self.path).content.decode())
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.path).status_code, 404)
        self.assertEqual(self.client.get(f"/api/v1/seller/stores/{self.seller.pk}/finance/").status_code, 404)


class PerformancePrivacyTests(TestCase):
    def test_seller_report_is_membership_scoped(self):
        from django.contrib.auth import get_user_model
        from sellers.models import Seller, SellerMembership
        user = get_user_model().objects.create_user("09123456970")
        seller = Seller.objects.create(name="Mine", status="approved")
        other = Seller.objects.create(name="Other", status="approved")
        SellerMembership.objects.create(user=user, seller=seller, role="owner")
        self.client.force_login(user)
        own = self.client.get(f"/api/v1/seller/stores/{seller.pk}/performance/")
        self.assertEqual(own.status_code, 200)
        self.assertEqual(own.json()["paid_orders"], 0)
        self.assertEqual(self.client.get(f"/api/v1/seller/stores/{other.pk}/performance/").status_code, 404)
        self.assertEqual(self.client.get(f"/api/v1/operations/reports/sellers/{seller.pk}/").status_code, 403)
