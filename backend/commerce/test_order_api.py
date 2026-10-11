import json
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from sellers.models import Seller, SellerMembership
from .test_fulfillment import FulfillmentTests
from .models import Order
from operations.models import AuditEvent


class OrderApiTests(TestCase):
    def setUp(self):
        FulfillmentTests.setUp(self)
        self.order.status = Order.Status.PAID
        self.order.save(update_fields=["status"])
        self.owner = get_user_model().objects.create_user("09123456911")
        self.other_owner = get_user_model().objects.create_user("09123456912")
        SellerMembership.objects.create(user=self.owner, seller=self.delivery.seller, role="owner")
        other_seller = Seller.objects.create(name="Other")
        SellerMembership.objects.create(user=self.other_owner, seller=other_seller, role="owner")
        self.manager = get_user_model().objects.create_user("09123456913", is_staff=True)
        self.manager.groups.add(Group.objects.create(name="marketplace_manager"))

    def test_seller_ownership_and_staff_delivery_confirmation(self):
        seller_id = self.delivery.seller_id
        path = f"/api/v1/seller/stores/{seller_id}/deliveries/{self.delivery.pk}/transition/"
        self.client.force_login(self.other_owner)
        self.assertEqual(self.client.post(path, json.dumps({"status": "packing"}), content_type="application/json").status_code, 404)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(f"/api/v1/seller/stores/{seller_id}/deliveries/").json()["deliveries"][0]["id"], self.delivery.pk)
        for payload in ({"status": "packing"}, {"status": "shipped", "tracking_code": "TRACK"}):
            self.assertEqual(self.client.post(path, json.dumps(payload), content_type="application/json").status_code, 200)
        self.assertEqual(self.client.post(path, json.dumps({"status": "delivered"}), content_type="application/json").status_code, 400)
        self.client.force_login(self.manager)
        response = self.client.post(f"/api/v1/operations/deliveries/{self.delivery.pk}/transition/", json.dumps({"status": "delivered", "reason": "Carrier delivery confirmed"}), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(AuditEvent.objects.get().after["status"], "delivered")

    def test_buyer_cannot_open_admin_orders(self):
        self.client.force_login(self.buyer)
        self.assertEqual(self.client.get("/api/v1/operations/orders/").status_code, 403)
