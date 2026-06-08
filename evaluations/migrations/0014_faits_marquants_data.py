"""Migre l'ancien texte 'faits_marquants' en une première ligne FaitMarquant
+ corrige les évaluations où le champ 'evaluateur' est vide alors que le
collaborateur a un évaluateur attitré.
"""
from django.db import migrations


def migrer(apps, schema_editor):
    Evaluation = apps.get_model("evaluations", "Evaluation")
    FaitMarquant = apps.get_model("evaluations", "FaitMarquant")
    for ev in Evaluation.objects.all():
        # 1. Copier le texte existant dans une ligne FaitMarquant
        txt = (ev.faits_marquants or "").strip()
        if txt and not FaitMarquant.objects.filter(evaluation=ev).exists():
            FaitMarquant.objects.create(evaluation=ev, ordre=1, fait=txt, observation="")
        # 2. Si le champ evaluateur est vide mais le collaborateur a un évaluateur,
        #    on remplit (nom complet ou email).
        if not (ev.evaluateur or "").strip() and ev.collaborateur.evaluateur_id:
            u = ev.collaborateur.evaluateur
            full = f"{u.first_name} {u.last_name}".strip()
            ev.evaluateur = full or u.email
            ev.save(update_fields=["evaluateur"])


def revert(apps, schema_editor):
    FaitMarquant = apps.get_model("evaluations", "FaitMarquant")
    FaitMarquant.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [("evaluations", "0013_faitmarquant")]
    operations = [migrations.RunPython(migrer, revert)]
