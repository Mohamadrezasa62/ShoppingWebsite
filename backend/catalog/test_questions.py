import json
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, Client
from .models import Brand, Category, Product, ProductQuestion
from operations.models import AuditEvent


class QuestionTests(TestCase):
    def setUp(self):
        self.buyer = get_user_model().objects.create_user("09123456901")
        self.staff = get_user_model().objects.create_user("09123456902", is_staff=True)
        self.staff.groups.add(Group.objects.create(name="support_agent"))
        self.product = Product.objects.create(title="Phone", slug="phone", category=Category.objects.create(name="Phone", slug="phone"), status="published")
        self.path = f"/api/v1/catalog/questions/{self.product.pk}/"

    def post(self, path, data):
        return self.client.post(path, json.dumps(data), content_type="application/json")

    def test_publication_requires_authorized_answer_and_does_not_expose_identity(self):
        self.assertEqual(self.post(self.path, {"body": "Does this have warranty?"}).status_code, 401)
        self.client.force_login(self.buyer)
        result = self.post(self.path, {"body": "Does this have warranty?"})
        self.assertEqual(result.status_code, 201)
        qid = result.json()["question"]["id"]
        self.assertEqual(self.client.get(self.path).json()["questions"], [])
        decision = f"/api/v1/operations/questions/{qid}/decision/"
        self.assertEqual(self.post(decision, {"status": "published", "answer": "Yes", "reason": "Reviewed"}).status_code, 403)
        self.client.force_login(self.staff)
        self.assertEqual(self.post(decision, {"status": "published", "reason": "Reviewed"}).status_code, 400)
        self.assertEqual(self.post(decision, {"status": "published", "answer": "Check the offer warranty", "reason": "Reviewed"}).status_code, 200)
        public = self.client.get(self.path).json()["questions"]
        self.assertEqual(set(public[0]), {"id", "body", "answer"})
        self.assertEqual(ProductQuestion.objects.get().answered_by, self.staff)
        self.assertTrue(AuditEvent.objects.filter(action="question_moderated").exists())
        self.post(decision, {"status": "rejected", "reason": "Outdated"})
        self.assertEqual(self.client.get(self.path).json()["questions"], [])

    def test_pending_limit_validation_and_hidden_products(self):
        self.client.force_login(self.buyer)
        for bad in (None, [], "short", "x" * 2001):
            self.assertEqual(self.post(self.path, {"body": bad}).status_code, 400)
        for _ in range(3):
            self.assertEqual(self.post(self.path, {"body": "Does this have warranty?"}).status_code, 201)
        self.assertEqual(self.post(self.path, {"body": "Does this have warranty?"}).status_code, 429)
        self.product.brand = Brand.objects.create(name="Hidden", slug="hidden", is_active=False)
        self.product.save()
        self.assertEqual(self.client.get(self.path).status_code, 404)

    def test_csrf_is_required_for_submission(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.buyer)
        self.assertEqual(client.post(self.path, json.dumps({"body": "Does this have warranty?"}), content_type="application/json").status_code, 403)
