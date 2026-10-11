from io import BytesIO
import json
import tempfile
from PIL import Image, PngImagePlugin
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from catalog.models import ProductMedia
from commerce import tests as cart_fixtures


class MediaTests(TestCase):
    def setUp(self):
        cart_fixtures.CartTests.setUp(self)
        self.admin = get_user_model().objects.create_superuser("09123456890", "local-test-password")
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.settings_override = override_settings(MEDIA_ROOT=self.directory.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.path = f"/api/v1/operations/products/{self.offer.variant.product_id}/media/"

    def image(self):
        stream = BytesIO()
        metadata = PngImagePlugin.PngInfo()
        metadata.add_text("secret", "metadata-to-strip")
        Image.new("RGB", (10, 10), "red").save(stream, format="PNG", pnginfo=metadata)
        return SimpleUploadedFile("untrusted.html", stream.getvalue(), content_type="text/html")

    def test_upload_normalizes_pixels_and_requires_explicit_publication(self):
        self.client.force_login(self.admin)
        response = self.client.post(self.path, {"image": self.image(), "alt_text": "Phone", "reason": "New image"})
        self.assertEqual(response.status_code, 201)
        row = ProductMedia.objects.get()
        self.assertTrue(row.image.name.endswith(".png"))
        with Image.open(row.image.path) as image:
            self.assertNotIn("secret", image.info)
        public = f"/api/v1/catalog/media/{row.pk}/"
        self.assertEqual(self.client.get(public).status_code, 404)
        self.assertEqual(self.client.patch(f"/api/v1/operations/media/{row.pk}/", json.dumps({"approved": True, "reason": "Image reviewed"}), content_type="application/json").status_code, 200)
        response = self.client.get(public)
        self.assertEqual(response.status_code, 200)
        response.close()
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(f"/api/v1/operations/media/{row.pk}/preview/").status_code, 403)

    def test_invalid_images_and_customer_uploads_are_rejected(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(self.path, {"image": self.image(), "alt_text": "Phone", "reason": "New image"}).status_code, 403)
        self.client.force_login(self.admin)
        result = self.client.post(self.path, {"image": SimpleUploadedFile("image.svg", b"<svg><script>alert(1)</script></svg>"), "alt_text": "Phone", "reason": "New image"})
        self.assertEqual(result.status_code, 400)
        self.assertFalse(ProductMedia.objects.exists())
