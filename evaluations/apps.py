from django.apps import AppConfig


class EvaluationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "evaluations"

    def ready(self):
        # Importe les signaux d'audit (ils s'enregistrent au chargement du module).
        from . import audit  # noqa: F401
