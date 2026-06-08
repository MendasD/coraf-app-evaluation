"""Renomme deux unités pour plus de clarté."""
from django.db import migrations

RENAMES = [
    ("KM", "Gestionnaire de connaissances (KM)"),
    ("ME", "Spécialiste suivi évaluation (M&E)"),
]


def renomme(apps, schema_editor):
    Unite = apps.get_model("evaluations", "Unite")
    for code, libelle in RENAMES:
        Unite.objects.filter(code=code).update(libelle=libelle)


def revert(apps, schema_editor):
    Unite = apps.get_model("evaluations", "Unite")
    Unite.objects.filter(code="KM").update(libelle="KM")
    Unite.objects.filter(code="ME").update(libelle="M&E")


class Migration(migrations.Migration):
    dependencies = [("evaluations", "0009_seed_unites_et_catalogue")]
    operations = [migrations.RunPython(renomme, revert)]
