import os
from concurrent.futures import ThreadPoolExecutor
from unittest import skipUnless
from unittest.mock import patch
from uuid import uuid4
from django.core.cache import cache
from django.test import SimpleTestCase, RequestFactory
from .services import _code_digest, consume_code, TooManyRequests
from .throttling import limit_peer


@skipUnless(os.environ.get("AUTH_REDIS_TEST_URL"), "Set AUTH_REDIS_TEST_URL to an isolated Redis instance")
class RedisAuthenticationConcurrencyTests(SimpleTestCase):
    def setUp(self):
        self.override = self.settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": os.environ["AUTH_REDIS_TEST_URL"], "KEY_PREFIX": f"auth-test-{uuid4()}"}})
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(cache.close)
        # Never flush a configured Redis instance; unique prefixes isolate tests.

    def test_one_nonce_is_consumed_once_across_parallel_cache_clients(self):
        phone, code = "+989123456199", "123456"
        cache.set(f"otp:code:{phone}", {"digest": _code_digest(phone, code), "nonce": "parallel"}, 300)
        def consume(_):
            try:
                return consume_code(phone, expected_nonce="parallel", code=code)
            finally:
                cache.close()
        with ThreadPoolExecutor(max_workers=8) as pool:
            result = list(pool.map(consume, range(16)))
        self.assertEqual(sum(bool(value) for value in result), 1)

    def test_parallel_rate_counters_enforce_peer_budget(self):
        def check(_):
            try:
                limit_peer(RequestFactory().post("/", REMOTE_ADDR="192.0.2.199"), "request")
                return True
            except TooManyRequests:
                return False
            finally:
                cache.close()
        with patch("accounts.throttling.time.time", return_value=1700000100), ThreadPoolExecutor(max_workers=8) as pool:
            result = list(pool.map(check, range(40)))
        self.assertEqual(sum(result), 20)
