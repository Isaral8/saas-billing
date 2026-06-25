from pathlib import Path
from decouple import config, UndefinedValueError

BASE_DIR = Path(__file__).resolve().parent.parent

try:
    SECRET_KEY = config('SECRET_KEY')
except UndefinedValueError:
    SECRET_KEY = 'django-insecure-dev-key-change-this-before-going-live'

DEBUG = config('DEBUG', default=True, cast=bool)
ALLOWED_HOSTS = config(
    'ALLOWED_HOSTS',
    default='localhost,127.0.0.1,.localhost',
    cast=lambda v: [s.strip() for s in v.split(',')]
)

# ===================================
# APPS
# ===================================
SHARED_APPS = (
    'django_tenants',               # must be first
    'tenants',                      # holds Client/Domain models

    'django.contrib.contenttypes',  # must come before auth
    'django.contrib.auth',
    'django.contrib.admin',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',

    'rest_framework',

    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.microsoft',
    'tickets',

    'accounts',                     # CustomUser — must come after allauth
    'automation',
    'django_celery_beat',
    'django_celery_results',
)

TENANT_APPS = (
    'billing',                      # django_tenants requires at least one app
)

INSTALLED_APPS = list(SHARED_APPS) + [
    app for app in TENANT_APPS if app not in SHARED_APPS
]

SITE_ID = 1

# ===================================
# MIDDLEWARE
# ===================================
MIDDLEWARE = [
    'django_tenants.middleware.main.TenantMainMiddleware',  # must be first
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

# ===================================
# TEMPLATES
# ===================================
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

# ===================================
# MULTI-TENANCY
# ===================================
TENANT_MODEL        = 'tenants.Client'
TENANT_DOMAIN_MODEL = 'tenants.Domain'

# ===================================
# DATABASE
# ===================================
DATABASES = {
    'default': {
        'ENGINE':   'django_tenants.postgresql_backend',
        'NAME':     config('DB_NAME',     default='isaral_db'),
        'USER':     config('DB_USER',     default='postgres'),
        'PASSWORD': config('DB_PASSWORD', default='postgres'),
        'HOST':     config('DB_HOST',     default='localhost'),
        'PORT':     config('DB_PORT',     default='5432'),
    }
}
DATABASE_ROUTERS = ('django_tenants.routers.TenantSyncRouter',)

# ===================================
# PASSWORD VALIDATION
# ===================================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 8},
    },
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ===================================
# INTERNATIONALISATION
# ===================================
LANGUAGE_CODE = 'en-us'
TIME_ZONE     = 'Asia/Kolkata'
USE_I18N      = True
USE_TZ        = True

# ===================================
# STATIC & MEDIA
# ===================================
STATIC_URL       = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT      = BASE_DIR / 'staticfiles'

MEDIA_URL  = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ===================================
# AUTHENTICATION
# ===================================
AUTH_USER_MODEL = 'accounts.CustomUser'

AUTHENTICATION_BACKENDS = [
    'accounts.backends.EmailAuthBackend',
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

LOGIN_URL           = '/accounts/login/'
LOGIN_REDIRECT_URL  = '/accounts/dashboard/'
LOGOUT_REDIRECT_URL = '/accounts/login/'    # ← fixed: 'home' doesn't exist as a named URL

# ===================================
# ALLAUTH
# ===================================
# ← fixed: replaced 3 deprecated settings with the 2 new ones
ACCOUNT_LOGIN_METHODS  = {'email'}
ACCOUNT_SIGNUP_FIELDS  = ['email*', 'password1*', 'password2*']
ACCOUNT_UNIQUE_EMAIL   = True
ACCOUNT_USER_MODEL_USERNAME_FIELD = None

ACCOUNT_ADAPTER     = 'accounts.adapters.AccountAdapter'
SOCIALACCOUNT_ADAPTER = 'accounts.adapters.SocialAccountAdapter'

SOCIALACCOUNT_LOGIN_ON_GET                    = True
SOCIALACCOUNT_AUTO_SIGNUP                     = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION            = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'APPS': [{
            'client_id': config('GOOGLE_CLIENT_ID',     default=''),
            'secret':    config('GOOGLE_CLIENT_SECRET', default=''),
            'key':       '',
        }],
        'SCOPE':       ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
    },
    'microsoft': {
        'APPS': [{
            'client_id': config('MICROSOFT_CLIENT_ID',     default=''),
            'secret':    config('MICROSOFT_CLIENT_SECRET', default=''),
            'key':       '',
        }],
        'SCOPE':  ['User.Read'],
        'TENANT': 'common',
    },
}

# ===================================
# EMAIL
# ===================================
if DEBUG:
    EMAIL_BACKEND    = 'django.core.mail.backends.console.EmailBackend'
    DEFAULT_FROM_EMAIL = 'noreply@isaral.local'
    SERVER_EMAIL     = 'noreply@isaral.local'
else:
    EMAIL_BACKEND       = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST          = config('EMAIL_HOST',     default='smtp.gmail.com')
    EMAIL_PORT          = config('EMAIL_PORT',     default=587, cast=int)
    EMAIL_USE_TLS       = config('EMAIL_USE_TLS',  default=True, cast=bool)
    EMAIL_HOST_USER     = config('EMAIL_HOST_USER')
    EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD')
    DEFAULT_FROM_EMAIL  = f'iSaral Business Solutions <{EMAIL_HOST_USER}>'
    SERVER_EMAIL        = EMAIL_HOST_USER

EMAIL_SUBJECT_PREFIX = '[iSaral] '
EMAIL_TIMEOUT        = 10

# ===================================
# REST FRAMEWORK
# ===================================
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

# ===================================
# SESSION
# ===================================
SESSION_COOKIE_SECURE        = not DEBUG
SESSION_COOKIE_HTTPONLY      = True
SESSION_COOKIE_AGE           = 1209600  # 2 weeks
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# ===================================
# SECURITY
# ===================================
CSRF_COOKIE_SECURE  = not DEBUG
CSRF_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS     = 'DENY'

if not DEBUG:
    SECURE_SSL_REDIRECT            = True
    SECURE_HSTS_SECONDS            = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD            = True

# ===================================
# CELERY CONFIGURATION
# ===================================
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'django-db'
CELERY_CACHE_BACKEND = 'django-cache'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Asia/Kolkata'
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60
