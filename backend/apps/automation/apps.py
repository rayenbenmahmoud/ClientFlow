from django.apps import AppConfig


class AutomationConfig(AppConfig):
    name = "apps.automation"

    def ready(self):
        from . import signals  # noqa: F401  (registers workflow receivers)
