"""Local-only defaults. Production requires explicit secrets and operational review."""
import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = os.environ.get('DJANGO_DEBUG', '1') == '1'
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'local-development-only-not-for-deployment')
if not DEBUG and SECRET_KEY == 'local-development-only-not-for-deployment':
    raise ImproperlyConfigured('Set DJANGO_SECRET_KEY outside local development.')
ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1,testserver').split(',')
INSTALLED_APPS = [
    'django.contrib.auth', 'django.contrib.contenttypes', 'django.contrib.sessions',
    'rest_framework', 'drf_spectacular', 'common', 'families', 'operations', 'incidents',
]
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware', 'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.middleware.common.CommonMiddleware', 'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware', 'common.middleware.PrivateAPIResponses',
]
ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'db.sqlite3', 'OPTIONS': {'timeout': 20}}}
if os.environ.get('POSTGRES_DB'):
    DATABASES['default'] = {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ['POSTGRES_DB'], 'USER': os.environ.get('POSTGRES_USER', 'lifealert'),
        'PASSWORD': os.environ.get('POSTGRES_PASSWORD', ''), 'HOST': os.environ.get('POSTGRES_HOST', 'localhost'),
        'PORT': os.environ.get('POSTGRES_PORT', '5432'),
    }
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'common.schema.ContractSchema',
    'EXCEPTION_HANDLER': 'common.exceptions.api_exception_handler',
    'DEFAULT_AUTHENTICATION_CLASSES': ['families.authentication.DeviceAuthentication', 'common.identity.AdultBearerAuthentication', 'rest_framework.authentication.SessionAuthentication'],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated', 'common.mfa.StaffMFAPermission'],
    'DEFAULT_RENDERER_CLASSES': ['rest_framework.renderers.JSONRenderer'],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination', 'PAGE_SIZE': 50,
    'DEFAULT_THROTTLE_CLASSES': ['rest_framework.throttling.UserRateThrottle'],
    'DEFAULT_THROTTLE_RATES': {'user': '120/min','identity':'10/min','recovery':'5/hour','pairing':'10/min'},
}
USE_TZ = True
TIME_ZONE = 'UTC'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
MEDIA_ROOT = BASE_DIR / 'private-media'  # Never exposed as a public URL.
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024
CONTINUE_ACCEPTED_INCIDENTS = os.environ.get('CONTINUE_ACCEPTED_INCIDENTS', '1') == '1'
# Development thresholds, not approved service promises.
LOCATION_MAX_AGE_SECONDS = int(os.environ.get('LOCATION_MAX_AGE_SECONDS', '300'))
LOCATION_MAX_ACCURACY_METERS = int(os.environ.get('LOCATION_MAX_ACCURACY_METERS', '200'))
CREW_OFFER_SECONDS = int(os.environ.get('CREW_OFFER_SECONDS', '120'))
SIMULATED_EMS_OUTCOME = os.environ.get('SIMULATED_EMS_OUTCOME', 'acknowledged')
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
if not DEBUG:
    SECURE_SSL_REDIRECT = True
# Do not emit request payloads, tokens, location, media or care profiles to logs.
LOGGING = {'version': 1, 'disable_existing_loggers': False,
           'handlers': {'null': {'class': 'logging.NullHandler'}},
           'loggers': {'django.request': {'handlers': ['null'], 'propagate': False}}}

# Local simulation mechanics only; these are not operational SLA targets.
SIM_NOTIFICATION_MAX_ATTEMPTS = int(os.environ.get('SIM_NOTIFICATION_MAX_ATTEMPTS', '3'))
SIM_NOTIFICATION_RETRY_SECONDS = int(os.environ.get('SIM_NOTIFICATION_RETRY_SECONDS', '5'))
SIM_NOTIFICATION_LEASE_SECONDS = int(os.environ.get('SIM_NOTIFICATION_LEASE_SECONDS', '60'))
SIM_NOTIFICATION_OUTCOME = os.environ.get('SIM_NOTIFICATION_OUTCOME', 'success')
if min(SIM_NOTIFICATION_MAX_ATTEMPTS, SIM_NOTIFICATION_RETRY_SECONDS, SIM_NOTIFICATION_LEASE_SECONDS) < 1:
    raise ImproperlyConfigured('Simulation attempt/retry/lease values must be positive.')

CAREGIVER_INVITE_SECONDS = int(os.environ.get('CAREGIVER_INVITE_SECONDS', '86400'))

# Security lifetimes, not emergency-response promises. All are configurable.
ADULT_ACCESS_SECONDS = int(os.environ.get('ADULT_ACCESS_SECONDS','3600'))
ADULT_REFRESH_SECONDS = int(os.environ.get('ADULT_REFRESH_SECONDS','604800'))
ACCOUNT_CHALLENGE_SECONDS = int(os.environ.get('ACCOUNT_CHALLENGE_SECONDS','1800'))
REQUIRE_VERIFIED_ADULT_CONTACT = not DEBUG

if min(CAREGIVER_INVITE_SECONDS, ADULT_ACCESS_SECONDS, ADULT_REFRESH_SECONDS, ACCOUNT_CHALLENGE_SECONDS) < 1:
    raise ImproperlyConfigured('Identity lifetimes must be positive.')

DEVICE_PAIRING_SECONDS = int(os.environ.get('DEVICE_PAIRING_SECONDS','600'))
# 0 preserves explicit revocation-based child access; a nonzero expiry is optional.
DEVICE_TOKEN_SECONDS = int(os.environ.get('DEVICE_TOKEN_SECONDS','0'))
if DEVICE_PAIRING_SECONDS < 1 or DEVICE_TOKEN_SECONDS < 0:
    raise ImproperlyConfigured('Device pairing/credential lifetimes are invalid.')

ENFORCE_STAFF_MFA = not DEBUG
STAFF_MFA_SECONDS = int(os.environ.get("STAFF_MFA_SECONDS", "43200"))
STAFF_MFA_ENROLL_SECONDS = int(os.environ.get("STAFF_MFA_ENROLL_SECONDS", "600"))
if min(STAFF_MFA_SECONDS, STAFF_MFA_ENROLL_SECONDS) < 1:
    raise ImproperlyConfigured("MFA lifetimes must be positive.")

SPECTACULAR_SETTINGS = {
    'TITLE': 'Life alert local backend',
    'DESCRIPTION': 'Local simulation and manual evidence API. No live messaging, payment or emergency dispatch.',
    'VERSION': '0.3.0',
    'COMPONENT_SPLIT_REQUEST': True,
    'SERVE_INCLUDE_SCHEMA': False,
    'SERVE_PERMISSIONS': ['rest_framework.permissions.IsAuthenticated', 'common.mfa.StaffMFAPermission'],
    'ENUM_NAME_OVERRIDES': {'PrivacyRequestKind':['export','correction','media_delete','account_close'], 'CareEventKind':['support','observation','handover_note'], 'HandoverDecision':['declined','cancelled'], 'IncidentTransition':['triage','active','resolved','cancelled'], 'EscalationTransition':['acknowledged','resolved'], 'AssignmentTransition':['accepted','declined','en_route','arrived','complete'], 'PlacementTransition':['intake','released','cancelled']},
}

# A shared throttle store is required across production API workers. Provision it
# with createcachetable; this is separate from migration readiness.
if not DEBUG:
    if len(SECRET_KEY) < 50:
        raise ImproperlyConfigured('Use a private DJANGO_SECRET_KEY of at least 50 characters.')
    if not os.environ.get('DJANGO_ALLOWED_HOSTS') or '*' in ALLOWED_HOSTS:
        raise ImproperlyConfigured('Set explicit production DJANGO_ALLOWED_HOSTS.')
    if DATABASES['default']['ENGINE'] != 'django.db.backends.postgresql':
        raise ImproperlyConfigured('Production requires PostgreSQL row locking.')
    CACHES = {'default': {'BACKEND':'django.core.cache.backends.db.DatabaseCache',
                          'LOCATION':'lifealert_throttle_cache'}}
SECURE_HSTS_SECONDS = 0 if DEBUG else 31536000
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
