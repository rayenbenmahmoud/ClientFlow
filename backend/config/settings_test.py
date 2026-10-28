"""Test settings: deterministic secret, fast hashing, relaxed login throttle."""

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-secret-key-not-for-real-use")
os.environ.setdefault("DJANGO_DEBUG", "true")

from .settings import *  # noqa: E402,F403

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
REST_FRAMEWORK = {**REST_FRAMEWORK, "DEFAULT_THROTTLE_RATES": {"login": "1000/min"}}  # noqa: F405
SECURE_SSL_REDIRECT = False
