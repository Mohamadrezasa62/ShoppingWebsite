import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from django.contrib.auth import get_user_model
from django.contrib.sessions.backends.db import SessionStore
from django.core.cache import cache
from django.db import connection, connections, transaction
from django.test import TransactionTestCase, RequestFactory
from .password_views import change_password
from .services import _code_digest


@skipUnless(connection.vendor == "postgresql", "Staff credential authority locks require PostgreSQL")
class StaffPasswordConcurrencyTests(TransactionTestCase):
    def test_demotion_and_password_change_serialize(self):
        cache.clear()
        user = get_user_model().objects.create_user("09123456198", "Original-Staff-Pass!19", is_staff=True)
        cache.set(f"otp:code:staff_password:{user.phone}", {"nonce": "rotation", "digest": _code_digest(user.phone, "123456", "staff_password")}, 300)
        gate = Barrier(2)
        def run(action):
            connections.close_all()
            try:
                gate.wait(timeout=10)
                return action()
            finally:
                connections.close_all()
        def rotate():
            request = RequestFactory().post("/password-test/", json.dumps({"current_password": "Original-Staff-Pass!19", "new_password": "Different-Staff-Pass!29", "code": "123456"}), content_type="application/json")
            request.user = get_user_model().objects.get(pk=user.pk)
            request.session = SessionStore()
            request._dont_enforce_csrf_checks = True
            return change_password(request).status_code
        def demote():
            with transaction.atomic():
                row = get_user_model().objects.select_for_update().get(pk=user.pk)
                row.is_staff = False
                row.save(update_fields=["is_staff"])
            return 200
        with ThreadPoolExecutor(max_workers=2) as pool:
            rotated, demoted = list(pool.map(run, [rotate, demote]))
        self.assertEqual(demoted, 200)
        self.assertIn(rotated, (200, 403))
        user.refresh_from_db()
        self.assertFalse(user.is_staff)
        self.assertTrue(user.check_password("Different-Staff-Pass!29" if rotated == 200 else "Original-Staff-Pass!19"))
        self.assertEqual(user.session_version, 1 if rotated == 200 else 0)
