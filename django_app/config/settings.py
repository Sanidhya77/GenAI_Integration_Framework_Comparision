"""
Django settings for the experiment.

Minimal configuration — only what is needed for the API endpoints.
Default middleware retained as specified in Chapter 3.
No database, no templates, no static files.
"""

import os
import sys

# Add project root to path so common/ is importable
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

SECRET_KEY = "thesis-experiment-not-for-production"

DEBUG = False

ALLOWED_HOSTS = ["*"]

# Default middleware configuration retained (session, security)
# as specified in the experiment context
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"

# No database needed for this experiment
DATABASES = {}

# No templates needed
TEMPLATES = []

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_TZ = True

# No static files
STATIC_URL = None