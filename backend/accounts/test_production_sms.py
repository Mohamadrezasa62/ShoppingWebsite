import json
from urllib.parse import parse_qs
from unittest.mock import MagicMock, patch
from django.core.cache import cache
from django.test import SimpleTestCase, override_settings, RequestFactory
from .sms import send_otp, DeliveryFailure, RejectRedirect
from .services import request_code, SmsUnavailable
from .throttling import client_identity, limit_peer
from .services import TooManyRequests, AuthenticationUnavailable


@override_settings(SMS_BACKEND='kavenegar', KAVENEGAR_API_KEY='a'*40, KAVENEGAR_LOGIN_TEMPLATE='customer-login', KAVENEGAR_STAFF_PASSWORD_TEMPLATE='staff-password')
class ProductionSmsTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def response(self, payload, status=200):
        response = MagicMock()
        response.status = status
        response.read.return_value = payload
        opener = MagicMock()
        opener.open.return_value.__enter__.return_value = response
        return opener

    def test_https_post_and_purpose_specific_templates(self):
        for purpose, template in [('login', 'customer-login'), ('staff_password', 'staff-password')]:
            opener = self.response(b'{"return":{"status":200}}')
            with patch('accounts.sms.build_opener', return_value=opener):
                send_otp('09123456931', '123456', purpose)
            request = opener.open.call_args.args[0]
            self.assertTrue(request.full_url.startswith('https://api.kavenegar.com/v1/'))
            self.assertEqual(request.get_method(), 'POST')
            self.assertNotIn('123456', request.full_url)
            self.assertEqual(parse_qs(request.data.decode()), {'receptor': ['09123456931'], 'token': ['123456'], 'template': [template], 'type': ['sms']})
            self.assertEqual(opener.open.call_args.kwargs['timeout'], 8)

    def test_rejections_invalid_json_and_oversized_responses_are_redacted(self):
        for payload in [b'{"return":{"status":403,"message":"private-code"}}', b'bad private-code', b'x'*65537, b'[]', b'{"return":{"status":true}}']:
            with patch('accounts.sms.build_opener', return_value=self.response(payload)):
                with self.assertRaises(DeliveryFailure) as result:
                    send_otp('09123456931', '123456', 'login')
                self.assertNotIn('private-code', str(result.exception))

    def test_timeout_is_not_retried_and_secret_is_not_propagated(self):
        opener = MagicMock()
        opener.open.side_effect = TimeoutError('API key and code private')
        with patch('accounts.sms.build_opener', return_value=opener):
            with self.assertRaisesMessage(DeliveryFailure, 'SMS submission failed'):
                send_otp('09123456931', '123456', 'login')
        self.assertEqual(opener.open.call_count, 1)

    def test_invalid_configuration_never_contacts_provider(self):
        with override_settings(KAVENEGAR_API_KEY='../../invalid'), patch('accounts.sms.build_opener') as transport:
            with self.assertRaises(DeliveryFailure):
                send_otp('09123456931', '123456', 'login')
            transport.assert_not_called()

    def test_failed_delivery_consumes_nonce_and_preserves_cooldown(self):
        with patch('accounts.sms.send_otp', side_effect=DeliveryFailure('private')):
            with self.assertRaises(SmsUnavailable):
                request_code('09123456931')
        record = cache.get('otp:code:09123456931')
        self.assertIsNotNone(record)
        self.assertTrue(cache.get(f'otp:consumed:09123456931:{record["nonce"]}'))
        with self.assertRaises(TooManyRequests):
            request_code('09123456931')

    def test_provider_acceptance_does_not_log_code(self):
        with patch('accounts.sms.build_opener', return_value=self.response(b'{"return":{"status":200}}')), patch('builtins.print') as log:
            request_code('09123456931')
            log.assert_not_called()

    def test_redirects_are_never_followed(self):
        self.assertIsNone(RejectRedirect().redirect_request(None, None, 302, '', {}, 'https://attacker.test/'))


class TrustedProxyIdentityTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()

    @override_settings(AUTH_TRUSTED_PROXY_NETWORKS=['172.30.91.10/32'])
    def test_only_trusted_peer_can_supply_single_client_ip(self):
        trusted = self.factory.get('/', REMOTE_ADDR='172.30.91.10', HTTP_X_REAL_IP='203.0.113.42', HTTP_X_FORWARDED_FOR='attacker')
        self.assertEqual(client_identity(trusted), '203.0.113.42')
        forged = self.factory.get('/', REMOTE_ADDR='172.30.91.11', HTTP_X_REAL_IP='203.0.113.42')
        self.assertEqual(client_identity(forged), '172.30.91.11')
        trusted.META['HTTP_X_REAL_IP'] = '1.2.3.4, 5.6.7.8'
        self.assertEqual(client_identity(trusted), 'unknown-proxied-client')

    @override_settings(AUTH_TRUSTED_PROXY_NETWORKS=['172.30.91.10/32'])
    def test_clients_behind_edge_have_independent_budgets(self):
        first = self.factory.get('/', REMOTE_ADDR='172.30.91.10', HTTP_X_REAL_IP='203.0.113.41')
        second = self.factory.get('/', REMOTE_ADDR='172.30.91.10', HTTP_X_REAL_IP='203.0.113.42')
        for _ in range(20):
            limit_peer(first, 'request')
        with self.assertRaises(TooManyRequests):
            limit_peer(first, 'request')
        limit_peer(second, 'request')

    @override_settings(AUTH_TRUSTED_PROXY_NETWORKS=[])
    def test_mapped_ipv6_and_untrusted_headers_normalize(self):
        request = self.factory.get('/', REMOTE_ADDR='::ffff:203.0.113.42', HTTP_X_REAL_IP='1.2.3.4')
        self.assertEqual(client_identity(request), '203.0.113.42')

    def test_invalid_or_universal_trust_fails_closed(self):
        request = self.factory.get('/', REMOTE_ADDR='203.0.113.42')
        for networks in [['0.0.0.0/0'], ['::/0'], ['bad-network']]:
            with override_settings(AUTH_TRUSTED_PROXY_NETWORKS=networks):
                with self.assertRaises(AuthenticationUnavailable):
                    limit_peer(request, 'request')
