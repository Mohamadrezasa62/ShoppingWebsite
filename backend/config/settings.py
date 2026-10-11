import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "unsafe-local-development-only")
SITE_URL = os.environ.get("SITE_URL", "http://localhost:5067")
DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = [host.strip() for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if host.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "accounts",
    "sellers",
    "catalog",
    "commerce",
    "payments",
    "operations",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "config.middleware.RequestContextMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "accounts.middleware.SessionRevocationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.debug",
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
WSGI_APPLICATION = "config.wsgi.application"
AUTH_USER_MODEL = "accounts.User"

DATABASES = {"default": {
    "ENGINE": "django.db.backends.postgresql",
    "NAME": os.environ.get("POSTGRES_DB", "shopping"),
    "USER": os.environ.get("POSTGRES_USER", "shopping"),
    "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
    "HOST": os.environ.get("DATABASE_HOST", "db"),
    "PORT": os.environ.get("DATABASE_PORT", "5432"),
}}

if os.environ.get("TEST_SQLITE") == "1":
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "test-local.sqlite3"}}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fa"
TIME_ZONE = "Asia/Tehran"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if origin.strip()]
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SECURE_SSL_REDIRECT = os.environ.get("DJANGO_SECURE_SSL_REDIRECT", "0") == "1"
SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_HSTS_SECONDS", "0"))
# Enable only behind a proxy that removes client-supplied forwarding headers.
if os.environ.get("DJANGO_TRUST_TLS_PROXY", "0") == "1":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {"marketplace.requests": {"handlers": ["console"], "level": os.environ.get("REQUEST_LOG_LEVEL", "WARNING"), "propagate": False}},
}
SMS_BACKEND = os.environ.get("SMS_BACKEND", "disabled")
KAVENEGAR_API_KEY = os.environ.get("KAVENEGAR_API_KEY", "")
KAVENEGAR_LOGIN_TEMPLATE = os.environ.get("KAVENEGAR_LOGIN_TEMPLATE", "")
KAVENEGAR_STAFF_PASSWORD_TEMPLATE = os.environ.get("KAVENEGAR_STAFF_PASSWORD_TEMPLATE", "")
AUTH_TRUSTED_PROXY_NETWORKS = [value.strip() for value in os.environ.get("AUTH_TRUSTED_PROXY_NETWORKS", "").split(",") if value.strip()]
ZARINPAL_ENABLED = os.environ.get("ZARINPAL_ENABLED", "0") == "1"
ZARINPAL_MERCHANT_ID = os.environ.get("ZARINPAL_MERCHANT_ID", "")
ENABLE_SANDBOX_PAYMENTS = os.environ.get("ENABLE_SANDBOX_PAYMENTS", "0") == "1"
if ENABLE_SANDBOX_PAYMENTS and not DEBUG:
    raise RuntimeError("Sandbox payments are permitted only with DJANGO_DEBUG=1")
if SMS_BACKEND == "console" and not DEBUG:
    raise RuntimeError("Console SMS backend is permitted only with DJANGO_DEBUG=1")

CACHES = {"default": {
    "BACKEND": "django.core.cache.backends.redis.RedisCache",
    "LOCATION": os.environ.get("REDIS_URL", "redis://redis:6379/0"),
}}
if os.environ.get("TEST_SQLITE") == "1":
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
}
CELERY_BROKER_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CELERY_BEAT_SCHEDULE = {
    "purge-expired-shopping-history": {"task": "catalog.tasks.purge_expired_history", "schedule": 3600.0},
    "check-product-alerts": {"task": "catalog.tasks.check_product_alerts", "schedule": 60.0},
    "process-internal-outbox": {"task": "operations.tasks.process_outbox", "schedule": 10.0},
    "expire-pending-orders": {"task": "commerce.tasks.expire_due_orders", "schedule": 60.0},
}

if not DEBUG and SECRET_KEY == "unsafe-local-development-only":
    raise RuntimeError("Set DJANGO_SECRET_KEY for non-development environments")
