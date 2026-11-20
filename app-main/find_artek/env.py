"""Helpers for reading settings from environment variables.

Kept free of Django settings access so the tests can call them directly (SimpleTestCase),
without reloading the settings module.
"""

import os

from django.core.exceptions import ImproperlyConfigured

TRUE_VALUES = ('true', '1', 'yes', 'on')
FALSE_VALUES = ('false', '0', 'no', 'off')


def env_bool(name, default, environ=None):
    """Boolean value of the environment variable ``name``.

    Case-insensitive, surrounding whitespace ignored. Unset or empty gives ``default``;
    true/1/yes/on give True; false/0/no/off give False. Any other value raises
    ImproperlyConfigured, so a typo stops the app at startup instead of silently
    switching a feature on or off. ``environ`` defaults to ``os.environ``.
    """
    environ = os.environ if environ is None else environ
    raw = environ.get(name)
    value = '' if raw is None else raw.strip().lower()
    if not value:
        return default
    if value in TRUE_VALUES:
        return True
    if value in FALSE_VALUES:
        return False
    raise ImproperlyConfigured(
        f"Environment variable {name} must be one of "
        f"{', '.join(TRUE_VALUES + FALSE_VALUES)} (case-insensitive) or empty; got {raw!r}.")
