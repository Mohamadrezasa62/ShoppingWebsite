import json
import tempfile
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4
from PIL import Image, PngImagePlugin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client, override_settings
from .models import Brand, ProductReview, ReviewMedia
from . import test_trust


class ReviewImageTests(TestCase):
    def setUp(self):
        test_trust.TrustTests.setUp(self)
        self.product.status = "published"
        self.product.save(update_fields=["status"])
        self.review = ProductReview.objects.create(user=self.buyer, product=self.product, rating=5, title="Good", body="Useful")
        self.other = get_user_model().objects.create_user("09123456401")
        self.staff = get_user_model().objects.create_user("09123456402", is_staff=True)
        self.staff.groups.add(Group.objects.get_or_create(name="support_agent")[0])
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        settings = override_settings(MEDIA_ROOT=self.directory.name)
        settings.enable()
        self.addCleanup(settings.disable)
        self.client.force_login(self.buyer)

    def image(self):
        result = BytesIO()
        metadata = PngImagePlugin.PngInfo()
        metadata.add_text("private", "location and source metadata")
        Image.new("RGB", (20, 20), "red").save(result, "PNG", pnginfo=metadata)
        return SimpleUploadedFile("image.png", result.getvalue(), content_type="image/png")

    def upload(self, key=None, **change):
        return self.client.post(f"/api/v1/catalog/my-reviews/{self.review.pk}/images/", {"request_key": str(key or uuid4()), "alt_text": "Product in use", "image": self.image(), **change})

    def moderate(self, image_id, status="approved"):
        self.client.force_login(self.staff)
        return self.client.post(f"/api/v1/operations/review-images/{image_id}/decision/", json.dumps({"status": status, "reason": "Image checked"}), content_type="application/json")

    def test_normalized_upload_is_idempotent_private_and_capped(self):
        key = uuid4()
        self.assertEqual(self.upload(key).status_code, 201)
        self.assertEqual(self.upload(key).status_code, 200)
        self.assertEqual(self.upload(key, alt_text="Changed description").status_code, 409)
        row = ReviewMedia.objects.get()
        with Image.open(row.image.path) as normalized:
            self.assertEqual(normalized.format, "PNG")
            self.assertNotIn("private", normalized.info)
        self.assertEqual(self.client.get(f"/api/v1/catalog/review-images/{row.pk}/").status_code, 404)
        self.assertEqual(self.client.get(f"/api/v1/catalog/review-images/{row.pk}/preview/").status_code, 200)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(f"/api/v1/catalog/review-images/{row.pk}/preview/").status_code, 404)
        self.assertEqual(self.upload().status_code, 404)
        self.assertEqual(self.client.get("/api/v1/catalog/my-reviews/").json()["reviews"], [])
        self.client.force_login(self.buyer)
        for _ in range(2):
            self.assertEqual(self.upload().status_code, 201)
        self.assertEqual(self.upload().status_code, 409)
        self.assertEqual(ReviewMedia.objects.count(), 3)

    def test_publication_requires_both_approvals_and_current_visibility(self):
        self.upload()
        row = ReviewMedia.objects.get()
        self.assertEqual(self.moderate(row.pk).status_code, 200)
        public_url = f"/api/v1/catalog/review-images/{row.pk}/"
        self.client.logout()
        self.assertEqual(self.client.get(public_url).status_code, 404)
        self.review.status = "published"
        self.review.save(update_fields=["status"])
        self.assertEqual(self.client.get(public_url).status_code, 200)
        data = self.client.get(f"/api/v1/catalog/reviews/{self.product.pk}/").json()
        self.assertEqual(data["reviews"][0]["images"][0]["url"], public_url)
        self.review.status = "rejected"
        self.review.save(update_fields=["status"])
        self.assertEqual(self.client.get(public_url).status_code, 404)
        self.review.status = "published"
        self.review.save(update_fields=["status"])
        self.product.brand = Brand.objects.create(name="Hidden brand", slug="hidden", is_active=False)
        self.product.save(update_fields=["brand"])
        self.assertEqual(self.client.get(public_url).status_code, 404)
        self.assertEqual(self.client.get(f"/api/v1/catalog/reviews/{self.product.pk}/").status_code, 404)

    def test_withdrawal_cannot_be_republished_and_export_is_metadata_only(self):
        self.upload()
        row = ReviewMedia.objects.get()
        url = f"/api/v1/catalog/review-images/{row.pk}/withdraw/"
        self.client.force_login(self.other)
        self.assertEqual(self.client.delete(url).status_code, 404)
        self.client.force_login(self.buyer)
        for _ in range(2):
            self.assertEqual(self.client.delete(url).status_code, 200)
        self.assertEqual(self.client.get(f"/api/v1/catalog/review-images/{row.pk}/preview/").status_code, 404)
        export = self.client.get("/api/v1/auth/export/").json()["review_images"]
        self.assertEqual(export[0]["status"], "withdrawn")
        self.assertNotIn("image", export[0])
        self.assertEqual(self.moderate(row.pk).status_code, 409)

    def test_csrf_invalid_files_and_rejected_review(self):
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.buyer)
        self.assertEqual(csrf.post(f"/api/v1/catalog/my-reviews/{self.review.pk}/images/", {"image": self.image()}).status_code, 403)
        self.assertEqual(self.upload(image=SimpleUploadedFile("evil.svg", b"<svg/>")).status_code, 400)
        self.assertEqual(self.upload(request_key="bad").status_code, 400)
        self.assertEqual(self.upload(alt_text="x\x00y").status_code, 400)
        self.review.status = "rejected"
        self.review.save(update_fields=["status"])
        self.assertEqual(self.upload().status_code, 409)
        self.assertFalse(ReviewMedia.objects.exists())

    def test_audit_failure_rolls_back_database_and_file(self):
        with patch("catalog.review_media_api._audit", side_effect=RuntimeError("audit failed")):
            with self.assertRaises(RuntimeError):
                self.upload()
        self.assertFalse(ReviewMedia.objects.exists())
        self.assertEqual([path for path in Path(self.directory.name).rglob("*") if path.is_file()], [])
