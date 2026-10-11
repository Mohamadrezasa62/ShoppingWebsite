import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import connection, connections
from django.test import TransactionTestCase, RequestFactory
from .content_api import update_page, restore
from .models import ContentPage, ContentRevision


@skipUnless(connection.vendor == "postgresql", "Content revision row locks require PostgreSQL")
class ContentConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.first = get_user_model().objects.create_user("09123456194", is_staff=True)
        self.second = get_user_model().objects.create_user("09123456195", is_staff=True)
        group = Group.objects.create(name="catalog_operator")
        self.first.groups.add(group)
        self.second.groups.add(group)
        self.page = ContentPage.objects.create(title="Guide", slug="race-guide", body="Original")
        ContentRevision.objects.create(page=self.page, version=1, snapshot={"title": "Guide", "slug": "race-guide", "body": "Original", "kind": "guide", "is_published": False}, reason="Original baseline")

    def race(self, actions):
        gate = Barrier(2)
        def run(action):
            connections.close_all()
            try:
                gate.wait(timeout=10)
                return action()
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(run, actions))

    def edit(self, user_id, title):
        request = RequestFactory().patch("/content-race/", json.dumps({"version": 1, "title": title, "reason": "Concurrent edit"}), content_type="application/json")
        request.user = get_user_model().objects.get(pk=user_id)
        request._dont_enforce_csrf_checks = True
        return update_page(request, self.page.pk).status_code

    def test_two_editors_cannot_overwrite_same_version(self):
        results = self.race([lambda: self.edit(self.first.pk, "First edit"), lambda: self.edit(self.second.pk, "Second edit")])
        self.assertEqual(sorted(results), [200, 409])
        self.page.refresh_from_db()
        self.assertEqual(self.page.version, 2)
        self.assertEqual(self.page.revisions.count(), 2)

    def test_restore_and_edit_cannot_both_consume_same_version(self):
        def restore_first():
            request = RequestFactory().post("/restore-race/", json.dumps({"version": 1, "restore_version": 1, "reason": "Concurrent restore"}), content_type="application/json")
            request.user = get_user_model().objects.get(pk=self.first.pk)
            request._dont_enforce_csrf_checks = True
            return restore(request, self.page.pk).status_code
        results = self.race([restore_first, lambda: self.edit(self.second.pk, "Changed guide")])
        self.assertEqual(sorted(results), [200, 409])
        self.page.refresh_from_db()
        self.assertEqual(self.page.version, 2)
        self.assertEqual(self.page.revisions.count(), 2)
