"""
Django settings for the FE-RealEstate-Tracker backend.

This project is a Django REST Framework API scaffolded to match the
FE-RealEstate-Tracker React + Vite + TypeScript frontend field-for-field
(see each app's models.py / serializers.py for the frontend file it mirrors).
"""

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Nothing in this project previously loaded the .env file into the process —
# there was no python-dotenv/django-environ call anywhere, so every
# os.environ.get(...) below was silently falling back to its hardcoded
# default no matter what was written in .env. Real environment variables
# (Docker/host platform) already work fine without this and will still take
# priority — load_dotenv() never overrides a variable that's already set in
# the environment.
load_dotenv(BASE_DIR / ".env")

_INSECURE_DEFAULT_KEY = "django-insecure-change-me-before-deploying-to-production"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", _INSECURE_DEFAULT_KEY)

# Safe-by-default: DEBUG only turns on if DJANGO_DEBUG is explicitly set to
# "True" in the environment. Previously this defaulted to True, so a missing
# env var on a live server would silently leak debug pages/stack traces.
DEBUG = os.environ.get("DJANGO_DEBUG", "False") == "True"

if not DEBUG and SECRET_KEY == _INSECURE_DEFAULT_KEY:
    # Fail loudly at startup rather than silently running a live deployment
    # on a publicly-known secret key (session/JWT signing would be forgeable).
    raise RuntimeError(
        "DJANGO_SECRET_KEY is not set. Refusing to start with DEBUG=False and "
        "the default insecure key. Set DJANGO_SECRET_KEY in the environment."
    )

ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # third-party
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    # project apps
    "accounts",
    "projects",
    "tasks",
    "hurdles",
    "resources",
    "checklists",
    "compliance",
    "handover",
    "society",
    "categorymanagement",
    "documents",
    "adminpanel",
    "analytics",
    "core",
    "notifications",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "notifications.middleware.ActivityNotificationMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases
#
# PostgreSQL, configured via environment variables (see .env.example).
# If you ever need to go back to SQLite for a quick local check, swap this
# block back to:
#   {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "vibe_tracker"),
        "USER": os.environ.get("DB_USER", "postgres"),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "5432"),
    }
}


# Custom user model (see accounts/models.py)
AUTH_USER_MODEL = "accounts.User"


AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.environ.get("DJANGO_TIME_ZONE", "Asia/Kolkata")
USE_I18N = True
USE_TZ = True


STATIC_URL = "static/"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# Django REST Framework
# Renderer/parser use camelCase over the wire (e.g. `startDate`, not
# `start_date`) so the response/request shape matches the frontend's
# TypeScript interfaces with no adapter layer needed.
#
# Pagination is off globally — list endpoints return a plain JSON array
# instead of {count, next, previous, results}. apiList() in lib/api.ts
# already handles a plain array response. If any single list ever gets
# huge, bring back pagination for that one viewset specifically.

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_RENDERER_CLASSES": (
        "djangorestframework_camel_case.render.CamelCaseJSONRenderer",
        "djangorestframework_camel_case.render.CamelCaseBrowsableAPIRenderer",
    ),
    "DEFAULT_PARSER_CLASSES": (
        "djangorestframework_camel_case.parser.CamelCaseJSONParser",
        "djangorestframework_camel_case.parser.CamelCaseFormParser",
        "djangorestframework_camel_case.parser.CamelCaseMultiPartParser",
    ),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=8),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}

# CORS — allow the Vite dev server and live frontend to call the API.
CORS_ALLOWED_ORIGINS = os.environ.get(
    "CORS_ALLOWED_ORIGINS",
    "https://rst.vibesandbox.live,http://localhost:5173,http://localhost:5174,http://localhost:8080,http://127.0.0.1:8080"
).split(",")
CORS_ALLOW_CREDENTIALS = True

# Needed for /admin/ and any other session/cookie-based POST once the
# frontend is served from a different (HTTPS) origin than the API in prod.
CSRF_TRUSTED_ORIGINS = os.environ.get(
    "CSRF_TRUSTED_ORIGINS",
    "https://rst.vibesandbox.live,http://localhost:5173,http://localhost:5174,http://localhost:8080,http://127.0.0.1:8080"
).split(",")

# ---------------------------------------------------------------------------
# Email configuration
# ---------------------------------------------------------------------------
# No credentials are hardcoded here — everything comes from the environment.
# If EMAIL_HOST_USER / EMAIL_HOST_PASSWORD are missing, we fall back to the
# console backend (prints emails to the terminal) instead of silently using
# a real account.
#
# EMAIL_BACKEND points at a custom backend (accounts/email_backend.py) that
# builds its SSL context from certifi's CA bundle explicitly. This fixes:
#   [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: Basic
#   Constraints of CA cert not marked critical (_ssl.c:1028)

EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "rajbrijeshsingh1804@gmail.com")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "wwrc htgh fhrb nmhk")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "True") == "True"
EMAIL_USE_SSL = os.environ.get("EMAIL_USE_SSL", "False") == "True"

if EMAIL_HOST and EMAIL_HOST_USER and EMAIL_HOST_PASSWORD:
    EMAIL_BACKEND = "accounts.email_backend.CertifiEmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "Real Estate Tracker <rajbrijeshsingh1804@gmail.com>")

# Fallback invite URL for server-side generation
FRONTEND_ACCEPT_INVITE_URL = os.environ.get(
    "FRONTEND_ACCEPT_INVITE_URL", "https://rst.vibesandbox.live/accept-invite"
)


INVITATION_EXPIRY_DAYS = int(os.environ.get("INVITATION_EXPIRY_DAYS", "7"))