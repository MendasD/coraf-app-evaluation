"""Pour les évaluations existantes déjà soumises/validées/visées, on utilise
la date de modification comme date de signature (approximatif mais utile pour
ne pas laisser ces dates vides sur les fiches déjà finalisées).
"""
from django.db import migrations


def backfill(apps, schema_editor):
    Evaluation = apps.get_model("evaluations", "Evaluation")
    for ev in Evaluation.objects.all():
        changed = []
        # Si déjà soumise ou plus avancée et pas de date_soumission, on copie
        if ev.statut in ("SOUMISE", "VALIDEE", "VISEE_RH") and not ev.date_soumission:
            ev.date_soumission = ev.date_modification
            changed.append("date_soumission")
        if ev.statut in ("VALIDEE", "VISEE_RH") and not ev.date_validation:
            ev.date_validation = ev.date_modification
            changed.append("date_validation")
        if ev.statut == "VISEE_RH" and not ev.date_visa_rh:
            ev.date_visa_rh = ev.date_modification
            changed.append("date_visa_rh")
        if changed:
            ev.save(update_fields=changed)


def revert(apps, schema_editor):
    pass  # rien à défaire (les colonnes sont droppées par la migration précédente)


class Migration(migrations.Migration):
    dependencies = [("evaluations", "0015_evaluation_date_soumission_and_more")]
    operations = [migrations.RunPython(backfill, revert)]
