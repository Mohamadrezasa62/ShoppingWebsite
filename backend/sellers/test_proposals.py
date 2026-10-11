import json
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from catalog.models import Category, Product, Variant
from .models import Seller, SellerMembership, ProductProposal


class ProposalTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("09123456831")
        self.staff = get_user_model().objects.create_user("09123456832", is_staff=True)
        self.staff.groups.add(Group.objects.create(name="catalog_operator"))
        self.seller = Seller.objects.create(name="Seller", status="approved")
        self.other = Seller.objects.create(name="Other", status="approved")
        SellerMembership.objects.create(user=self.user, seller=self.seller, role="owner")
        self.category = Category.objects.create(name="Phones", slug="phones")
        self.path = f"/api/v1/seller/stores/{self.seller.pk}/proposals/"
        self.client.force_login(self.user)

    def post(self, path, data):
        return self.client.post(path, json.dumps(data), content_type="application/json")

    def submit(self):
        return self.post(self.path, {"title": "New phone", "sku": "NEW-1", "category_id": self.category.pk})

    def test_proposals_do_not_publish_before_staff_review(self):
        result = self.submit()
        self.assertEqual(result.status_code, 201)
        self.assertFalse(Product.objects.exists())
        proposal = ProductProposal.objects.get()
        path = f"/api/v1/operations/proposals/{proposal.pk}/decision/"
        data = {"status": "approved", "slug": "new-phone", "reason": "Catalog checked"}
        self.assertEqual(self.post(path, data).status_code, 403)
        self.client.force_login(self.staff)
        self.assertEqual(self.post(path, data).status_code, 200)
        self.assertEqual(Product.objects.get().status, "draft")
        self.assertEqual(Variant.objects.get().sku, "NEW-1")
        self.assertEqual(self.post(path, data).status_code, 409)
        self.assertEqual(Product.objects.count(), 1)

    def test_failed_sku_approval_rolls_back_product_and_review(self):
        existing = Product.objects.create(title="Existing", slug="existing", category=self.category)
        Variant.objects.create(product=existing, sku="NEW-1")
        self.submit()
        proposal = ProductProposal.objects.get()
        self.client.force_login(self.staff)
        result = self.post(f"/api/v1/operations/proposals/{proposal.pk}/decision/", {"status": "approved", "slug": "new-phone", "reason": "Catalog checked"})
        self.assertEqual(result.status_code, 409)
        self.assertEqual(Product.objects.count(), 1)
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, "pending")
        self.assertIsNone(proposal.product_id)

    def test_seller_membership_and_suspension_are_enforced(self):
        self.assertEqual(self.client.get(f"/api/v1/seller/stores/{self.other.pk}/proposals/").status_code, 404)
        self.seller.status = "suspended"
        self.seller.save()
        self.assertEqual(self.submit().status_code, 403)
