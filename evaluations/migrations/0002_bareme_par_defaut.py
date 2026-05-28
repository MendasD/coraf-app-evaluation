from decimal import Decimal

from django.db import migrations

BAREME = [
    ("Excellent", 90, 100, "#15803d"),
    ("Très bien", 75, 89.99, "#22c55e"),
    ("Bien", 60, 74.99, "#eab308"),
    ("Passable", 50, 59.99, "#f97316"),
    ("Insuffisant", 0, 49.99, "#dc2626"),
]


def creer_bareme(apps, schema_editor):
    Niveau = apps.get_model("evaluations", "NiveauAppreciation")
    if Niveau.objects.exists():
        return
    for libelle, mn, mx, couleur in BAREME:
        Niveau.objects.create(
            libelle=libelle,
            seuil_min=Decimal(str(mn)),
            seuil_max=Decimal(str(mx)),
            couleur=couleur,
        )


def supprimer_bareme(apps, schema_editor):
    Niveau = apps.get_model("evaluations", "NiveauAppreciation")
    Niveau.objects.filter(libelle__in=[b[0] for b in BAREME]).delete()


class Migration(migrations.Migration):
    dependencies = [("evaluations", "0001_initial")]
    operations = [migrations.RunPython(creer_bareme, supprimer_bareme)]
