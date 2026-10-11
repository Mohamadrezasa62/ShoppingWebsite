import json
from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase, Client
from django.utils import timezone
from .models import ContentPage, ContentRevision, AuditEvent


class ContentEditorialTests(TestCase):
    def setUp(self):
        self.author = get_user_model().objects.create_user("09123456191", is_staff=True)
        self.author.groups.add(Group.objects.create(name="catalog_operator"))
        self.buyer = get_user_model().objects.create_user("09123456192")
        self.client.force_login(self.author)
        self.payload = {"title": "Buying guide", "slug": "buying-guide", "body": "Original text", "kind": "guide", "is_published": False, "reason": "Initial draft"}
        response = self.post("/api/v1/operations/pages/", self.payload)
        self.assertEqual(response.status_code, 201)
        self.page = ContentPage.objects.get(pk=response.json()["page"]["id"])
        self.path = f"/api/v1/operations/pages/{self.page.pk}/"

    def post(self, path, data):
        return self.client.post(path, json.dumps(data), content_type="application/json")

    def edit(self, **data):
        payload = {"version": self.page.version, "reason": "Editorial change", **data}
        response = self.client.patch(self.path, json.dumps(payload), content_type="application/json")
        self.page.refresh_from_db()
        return response

    def test_changes_create_immutable_versions_and_stale_editor_cannot_overwrite(self):
        self.assertEqual(self.edit(title="Revised title", body="Second text").status_code, 200)
        self.assertEqual(self.page.version, 2)
        response = self.edit(version=1, body="Lost update")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.page.body, "Second text")
        self.assertEqual(self.page.revisions.count(), 2)
        old = self.page.revisions.get(version=1)
        self.assertEqual(old.snapshot["body"], "Original text")
        old.reason = "Rewrite history"
        with self.assertRaises(ValidationError):
            old.save()
        self.assertEqual(AuditEvent.objects.filter(action="content_saved").count(), 2)

    def test_public_visibility_and_sitemap_obey_exact_schedule_boundaries(self):
        now = timezone.now()
        start, end = now+timedelta(hours=1), now+timedelta(hours=2)
        self.assertEqual(self.edit(is_published=True, publish_after=start.isoformat(), publish_until=end.isoformat()).status_code, 200)
        self.client.logout()
        for instant, visible in [(now, False), (start, True), (end-timedelta(microseconds=1), True), (end, False)]:
            with patch("django.utils.timezone.now", return_value=instant):
                self.assertEqual(self.client.get("/api/v1/operations/content/buying-guide/").status_code, 200 if visible else 404)
                self.assertEqual(bool(self.client.get("/api/v1/operations/content/").json()["pages"]), visible)
                self.assertEqual(bool(self.client.get("/api/v1/catalog/sitemap/").json()["pages"]), visible)
        self.client.force_login(self.author)
        self.assertEqual(self.client.get("/api/v1/operations/pages/").json()["pages"][0]["body"], "Original text")

    def test_public_payload_excludes_editorial_metadata_and_unpublish_wins(self):
        self.assertEqual(self.edit(is_published=True).status_code, 200)
        public = self.client.get("/api/v1/operations/content/buying-guide/").json()["page"]
        self.assertFalse({"version", "publish_after", "publish_until", "actor_id", "reason"}.intersection(public))
        self.assertEqual(self.edit(is_published=False).status_code, 200)
        self.assertEqual(self.client.get("/api/v1/operations/content/buying-guide/").status_code, 404)

    def test_restore_creates_unpublished_new_version_without_reactivating_schedule(self):
        self.edit(is_published=True, publish_until=(timezone.now()+timedelta(days=1)).isoformat())
        self.edit(body="Third text")
        response = self.post(self.path+"restore/", {"version": self.page.version, "restore_version": 2, "reason": "Restore approved text as draft"})
        self.assertEqual(response.status_code, 200)
        self.page.refresh_from_db()
        self.assertEqual(self.page.version, 4)
        self.assertEqual(self.page.body, "Original text")
        self.assertFalse(self.page.is_published)
        self.assertIsNone(self.page.publish_after)
        self.assertIsNone(self.page.publish_until)
        self.assertEqual(self.page.revisions.count(), 4)
        self.assertEqual(self.client.get("/api/v1/operations/content/buying-guide/").status_code, 404)
        self.assertEqual(self.post(self.path+"restore/", {"version": 3, "restore_version": 1, "reason": "Stale restore"}).status_code, 409)
        self.assertEqual(self.page.revisions.count(), 4)

    def test_restore_slug_collision_rolls_back_everything(self):
        self.edit(slug="new-guide")
        self.post("/api/v1/operations/pages/", {**self.payload, "title": "Another page"})
        response = self.post(self.path+"restore/", {"version": 2, "restore_version": 1, "reason": "Try historical slug"})
        self.assertEqual(response.status_code, 400)
        self.page.refresh_from_db()
        self.assertEqual(self.page.slug, "new-guide")
        self.assertEqual(self.page.version, 2)
        self.assertEqual(self.page.revisions.count(), 2)

    def test_invalid_windows_naive_times_versions_and_unknown_fields(self):
        start = timezone.now()
        for data in [{"publish_after": start.isoformat(), "publish_until": start.isoformat()},
                     {"publish_after": "2026-10-11T12:00"}, {"publish_after": True},
                     {"publish_after": "bad"}, {"version": True}, {"version": 0},
                     {"version": "1"}, {"unknown": "bad"}, {"body": "x"*50001}]:
            self.assertEqual(self.edit(**data).status_code, 400)
            self.assertEqual(self.page.version, 1)
        self.assertEqual(self.client.patch(self.path, json.dumps({"body": "Missing version", "reason": "Invalid patch"}), content_type="application/json").status_code, 400)
        self.assertEqual(self.page.revisions.count(), 1)

    def test_audit_failure_rolls_back_content_and_revision(self):
        with patch("operations.content_api._audit", side_effect=RuntimeError("Audit unavailable")):
            with self.assertRaises(RuntimeError):
                self.edit(body="Must roll back")
        self.page.refresh_from_db()
        self.assertEqual(self.page.body, "Original text")
        self.assertEqual(self.page.version, 1)
        self.assertEqual(self.page.revisions.count(), 1)

    def test_revisions_are_private_and_csrf_protected(self):
        self.client.force_login(self.buyer)
        self.assertEqual(self.client.get(self.path+"revisions/").status_code, 403)
        self.assertEqual(self.client.get("/api/v1/operations/pages/").status_code, 403)
        self.assertEqual(self.edit(body="Unauthorized").status_code, 403)
        self.assertEqual(self.post(self.path+"restore/", {"version": 1, "restore_version": 1, "reason": "Unauthorized restore"}).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(self.path+"revisions/").status_code, 401)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.author)
        self.assertEqual(csrf.patch(self.path, json.dumps({"version": 1, "is_published": True, "reason": "Publish"}), content_type="application/json").status_code, 403)
        self.assertEqual(csrf.post(self.path+"restore/", json.dumps({"version": 1, "restore_version": 1, "reason": "Restore"}), content_type="application/json").status_code, 403)
        self.assertEqual(self.page.revisions.count(), 1)

    def test_history_is_paginated_without_duplicates(self):
        for number in range(27):
            self.assertEqual(self.edit(body=f"Text {number}").status_code, 200)
        first = self.client.get(self.path+"revisions/")
        self.assertIn("no-store", first["Cache-Control"])
        first = first.json()
        self.assertEqual(len(first["revisions"]), 25)
        second = self.client.get(self.path+"revisions/", {"before": first["next_before"]}).json()
        self.assertEqual(len(second["revisions"]), 3)
        self.assertIsNone(second["next_before"])
        self.assertEqual(len({row["version"] for row in first["revisions"]+second["revisions"]}), 28)
        self.assertEqual(self.client.get(self.path+"revisions/", {"before": "-1"}).status_code, 400)

    def test_restore_cannot_use_revision_from_another_page(self):
        self.edit(body="Version two")
        other = self.post("/api/v1/operations/pages/", {**self.payload, "slug": "other-guide"}).json()["page"]
        self.assertEqual(self.post(f'/api/v1/operations/pages/{other["id"]}/restore/', {"version": 1, "restore_version": 2, "reason": "Foreign revision"}).status_code, 404)
        self.assertEqual(ContentPage.objects.get(pk=other["id"]).version, 1)

    def test_staff_page_list_is_paginated_and_rejects_invalid_page_numbers(self):
        ContentPage.objects.bulk_create([ContentPage(title=f"Guide {index}", slug=f"paged-guide-{index}", body="Draft") for index in range(30)])
        first = self.client.get("/api/v1/operations/pages/", {"page": 1}).json()
        second = self.client.get("/api/v1/operations/pages/", {"page": 2}).json()
        self.assertEqual(len(first["pages"]), 25)
        self.assertTrue(first["has_next"])
        self.assertEqual(len(second["pages"]), 6)
        self.assertFalse(second["has_next"])
        self.assertFalse({row["id"] for row in first["pages"]} & {row["id"] for row in second["pages"]})
        for value in ["0", "-1", "10001", "x"]:
            self.assertEqual(self.client.get("/api/v1/operations/pages/", {"page": value}).status_code, 400)
