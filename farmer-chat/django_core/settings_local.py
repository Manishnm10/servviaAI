# Use this overlay settings file to enable DRF templates without editing your base settings.
# Run the dev server with: python manage.py runserver --settings=django_core.settings_local

from .settings import *  # noqa

# Ensure Django REST Framework is installed for template discovery
if 'rest_framework' not in INSTALLED_APPS:
    INSTALLED_APPS = list(INSTALLED_APPS) + ['rest_framework']

# Renderers: keep Browsable API (needs DRF templates) and JSON
REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    # You can add other DRF settings here as needed
}

# Optional: make sure templates find app templates (default APP_DIRS=True already does this)
# TEMPLATES[0]['APP_DIRS'] = True  # noqa

# Optional: allow all hosts in dev (already allowed in your current settings)
ALLOWED_HOSTS = ['*']
