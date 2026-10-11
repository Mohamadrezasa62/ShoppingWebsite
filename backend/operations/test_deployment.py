from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from accounts.roles import STAFF_ROLES
from unittest.mock import patch, MagicMock
from django.core.management import call_command, CommandError
from django.test import SimpleTestCase, override_settings, RequestFactory
from config.urls import ready
from .management.commands.deployment_preflight import configuration_errors


SECURE = dict(
    DEBUG=False, SECRET_KEY='0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ',
    DATABASES={'default': {'ENGINE': 'django.db.backends.postgresql', 'PASSWORD': 'secure-db-password'}},
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.redis.RedisCache', 'LOCATION': 'redis://redis:6379/0'}},
    SITE_URL='https://shop.test', ALLOWED_HOSTS=['shop.test', 'api'], CSRF_TRUSTED_ORIGINS=['https://shop.test'],
    SECURE_SSL_REDIRECT=True, SESSION_COOKIE_SECURE=True, CSRF_COOKIE_SECURE=True,
    SECURE_HSTS_SECONDS=3600, ENABLE_SANDBOX_PAYMENTS=False, SMS_BACKEND='disabled', STATIC_ROOT='/tmp/static',
)


@override_settings(**SECURE)
class DeploymentConfigurationTests(SimpleTestCase):
    def test_valid_staging_configuration_does_not_claim_service_or_launch_checks(self):
        self.assertEqual(configuration_errors(), [])
        output = StringIO()
        call_command('deployment_preflight', stdout=output)
        self.assertIn('services not checked', output.getvalue())
        self.assertIn('launch is not accepted', output.getvalue())

    def test_launch_cannot_be_enabled_by_configuration_only(self):
        with self.assertRaisesMessage(CommandError, 'Live-commerce launch remains blocked'):
            call_command('deployment_preflight', launch=True)

    def test_insecure_configuration_rejected_without_secret_disclosure(self):
        cases = [dict(DEBUG=True), dict(SECRET_KEY='replace-with-super-secret-value'), dict(ALLOWED_HOSTS=['*']), dict(SITE_URL='http://shop.test'), dict(CSRF_TRUSTED_ORIGINS=['https://*.test']), dict(SECURE_HSTS_SECONDS=0), dict(SMS_BACKEND='console'), dict(ENABLE_SANDBOX_PAYMENTS=True), dict(SESSION_COOKIE_SECURE=False)]
        for values in cases:
            with self.subTest(values=values), override_settings(**values):
                with self.assertRaises(CommandError) as result:
                    call_command('deployment_preflight')
                self.assertNotIn('replace-with-super-secret-value', str(result.exception))

    def test_origin_credentials_and_paths_rejected(self):
        for origin in ('https://user:password@shop.test', 'https://shop.test/path', 'https://shop.test?secret=1', 'https://shop.example.com'):
            with self.subTest(origin=origin), override_settings(SITE_URL=origin):
                self.assertTrue(configuration_errors())

    def test_sqlite_and_process_local_cache_rejected(self):
        with override_settings(DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3'}}, CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}):
            self.assertIn('PostgreSQL is required', configuration_errors())
            self.assertIn('Shared Redis cache is required', configuration_errors())

    def test_service_failure_is_redacted(self):
        with patch('operations.management.commands.deployment_preflight.connection') as database:
            database.cursor.side_effect = RuntimeError('password=private-value')
            with self.assertRaisesMessage(CommandError, 'Service/storage verification failed') as result:
                call_command('deployment_preflight', services=True)
            self.assertNotIn('private-value', str(result.exception))

    def test_services_check_storage_static_roles_and_pending_migrations(self):
        target = 'operations.management.commands.deployment_preflight.'
        with TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory, STATIC_ROOT=directory):
            asset = Path(directory) / 'admin/css/base.css'
            asset.parent.mkdir(parents=True)
            asset.write_text('/* test asset */')
            with patch(target + 'connection') as database, patch(target + 'MigrationExecutor') as executor, patch(target + 'Group') as groups, patch(target + 'cache') as shared:
                database.cursor.return_value.__enter__.return_value.fetchone.return_value = (1,)
                executor.return_value.migration_plan.return_value = []
                groups.objects.filter.return_value.values_list.return_value = STAFF_ROLES
                shared.get.return_value = 'ok'
                output = StringIO()
                call_command('deployment_preflight', services=True, stdout=output)
                self.assertIn('services verified', output.getvalue())
                shared.delete.assert_called_once()
                self.assertFalse(list(Path(directory).glob('.deployment-probe-*')))
                executor.return_value.migration_plan.return_value = ['unapplied']
                with self.assertRaisesMessage(CommandError, 'Unapplied migrations remain'):
                    call_command('deployment_preflight', services=True)
                executor.return_value.migration_plan.return_value = []
                groups.objects.filter.return_value.values_list.return_value = []
                with self.assertRaisesMessage(CommandError, 'Required staff roles are missing'):
                    call_command('deployment_preflight', services=True)
                groups.objects.filter.return_value.values_list.return_value = STAFF_ROLES
                asset.unlink()
                with self.assertRaisesMessage(CommandError, 'Collected admin static assets are missing'):
                    call_command('deployment_preflight', services=True)


class ReadinessTests(SimpleTestCase):
    def test_readiness_executes_database_query(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = (1,)
        with patch('config.urls.connection') as factory, patch('config.urls.cache') as cache:
            factory.cursor.return_value.__enter__.return_value = cursor
            cache.get.return_value = 'ok'
            self.assertEqual(ready(RequestFactory().get('/ready/')).status_code, 200)
            cursor.execute.assert_called_once_with('SELECT 1')

    def test_database_and_cache_failures_return_503_without_details(self):
        with patch('config.urls.connection') as database:
            database.cursor.side_effect = RuntimeError('private connection secret')
            response = ready(RequestFactory().get('/ready/'))
            self.assertEqual(response.status_code, 503)
            self.assertNotIn(b'private', response.content)
        with patch('config.urls.connection') as factory, patch('config.urls.cache') as cache:
            factory.cursor.return_value.__enter__.return_value.fetchone.return_value = (1,)
            cache.get.return_value = None
            self.assertEqual(ready(RequestFactory().get('/ready/')).status_code, 503)
