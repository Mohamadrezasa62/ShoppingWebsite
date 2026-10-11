from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urlsplit
from django.conf import settings
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from accounts.roles import STAFF_ROLES


def placeholder(value):
    return not value or any(token in value.lower() for token in ('replace-with', 'unsafe-local', 'changeme', 'example'))


def configuration_errors():
    errors = []
    if settings.DEBUG:
        errors.append('DEBUG must be disabled')
    secret = settings.SECRET_KEY
    if placeholder(secret) or len(secret) < 50 or len(set(secret)) < 8:
        errors.append('A non-placeholder random SECRET_KEY of at least 50 characters is required')
    database = settings.DATABASES['default']
    if database['ENGINE'] != 'django.db.backends.postgresql':
        errors.append('PostgreSQL is required')
    if placeholder(database.get('PASSWORD', '')):
        errors.append('A non-placeholder PostgreSQL password is required')
    if settings.CACHES['default']['BACKEND'] != 'django.core.cache.backends.redis.RedisCache':
        errors.append('Shared Redis cache is required')
    try:
        site = urlsplit(settings.SITE_URL)
        site.port
    except ValueError:
        errors.append('SITE_URL is malformed')
        site = urlsplit('')
    if site.scheme != 'https' or not site.hostname or site.username or site.password or site.query or site.fragment or site.path not in ('', '/') or site.hostname in ('localhost', '127.0.0.1') or site.hostname.endswith('.example.com'):
        errors.append('SITE_URL must be the actual HTTPS site origin')
    hosts = settings.ALLOWED_HOSTS
    if not hosts or any(host in ('*', 'localhost', '127.0.0.1') or host.startswith('.') for host in hosts) or (site.hostname and site.hostname not in hosts):
        errors.append('ALLOWED_HOSTS must explicitly allow the site hostname without wildcards/local hosts')
    if settings.SITE_URL.rstrip('/') not in settings.CSRF_TRUSTED_ORIGINS or any(not origin.startswith('https://') or '*' in origin for origin in settings.CSRF_TRUSTED_ORIGINS):
        errors.append('CSRF_TRUSTED_ORIGINS must include the exact HTTPS site origin')
    if not settings.SECURE_SSL_REDIRECT or not settings.SESSION_COOKIE_SECURE or not settings.CSRF_COOKIE_SECURE:
        errors.append('HTTPS redirect and secure session/CSRF cookies are required')
    if settings.SECURE_HSTS_SECONDS < 3600:
        errors.append('HSTS must be configured for at least 3600 seconds')
    if settings.ENABLE_SANDBOX_PAYMENTS or settings.SMS_BACKEND == 'console':
        errors.append('Development payment/SMS transports must be disabled')
    if settings.SMS_BACKEND not in ('disabled', 'kavenegar'):
        errors.append('Unsupported production SMS backend')
    if settings.SMS_BACKEND == 'kavenegar':
        from accounts.sms import configuration_valid
        if not configuration_valid():
            errors.append('Kavenegar API key and both approved template names are required')
    import ipaddress
    try:
        networks = [ipaddress.ip_network(value, strict=True) for value in settings.AUTH_TRUSTED_PROXY_NETWORKS]
        if any(network.prefixlen == 0 for network in networks):
            raise ValueError()
    except ValueError:
        errors.append('Trusted auth proxy networks must be explicit valid networks, never all addresses')
    if settings.ZARINPAL_ENABLED:
        from payments.zarinpal import configuration_valid
        if not configuration_valid():
            errors.append('Zarinpal merchant UUID and HTTPS origin are required')
    if not settings.STATIC_ROOT:
        errors.append('STATIC_ROOT is required')
    return errors


class Command(BaseCommand):
    help = 'Read-only deployment configuration and optional service checks; never certifies live commerce'

    def add_arguments(self, parser):
        parser.add_argument('--services', action='store_true', help='Verify database, migrations, roles, Redis and writable shared storage')
        parser.add_argument('--launch', action='store_true', help='Require live-commerce launch gates (currently unavailable)')

    def handle(self, *args, **options):
        errors = configuration_errors()
        if errors:
            raise CommandError('Deployment configuration rejected:\n- ' + '\n- '.join(errors))
        if options['services']:
            try:
                with connection.cursor() as cursor:
                    cursor.execute('SELECT 1')
                    if cursor.fetchone() != (1,):
                        raise RuntimeError()
                executor = MigrationExecutor(connection)
                if executor.migration_plan(executor.loader.graph.leaf_nodes()):
                    raise CommandError('Unapplied migrations remain; run the release job first')
                if set(STAFF_ROLES) - set(Group.objects.filter(name__in=STAFF_ROLES).values_list('name', flat=True)):
                    raise CommandError('Required staff roles are missing; run seed_roles')
                import uuid
                key = f'deployment-probe:{uuid.uuid4().hex}'
                try:
                    cache.set(key, 'ok', 10)
                    if cache.get(key) != 'ok':
                        raise RuntimeError()
                finally:
                    cache.delete(key)
                for root in (settings.MEDIA_ROOT, settings.STATIC_ROOT):
                    # A temporary storage probe is removed immediately, no user data is touched.
                    with NamedTemporaryFile(prefix='.deployment-probe-', dir=Path(root)):
                        pass
                if not (Path(settings.STATIC_ROOT) / 'admin/css/base.css').is_file():
                    raise CommandError('Collected admin static assets are missing')
            except CommandError:
                raise
            except Exception:
                # Exception text can contain credentials/connection strings.
                raise CommandError('Service/storage verification failed; inspect private operator logs') from None
        if options['launch']:
            raise CommandError('Live-commerce launch remains blocked: verified SMS delivery, certified payment reconciliation, real refund/payout adapters, approved business policies and staging PostgreSQL/Redis/browser/load/restore evidence are not supplied')
        self.stdout.write(self.style.SUCCESS('Deployment configuration passed' + ('; services verified' if options['services'] else '; services not checked')))
        self.stdout.write('Infrastructure staging only: real commerce launch is not accepted. SMS provider: ' + settings.SMS_BACKEND + '; live delivery has not been verified by this command.')
