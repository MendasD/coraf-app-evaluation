"""Ajoute un UUID public sur les évaluations pour ne plus exposer le compteur séquentiel dans les URLs."""
import uuid

from django.db import migrations, models


def fill_uuids(apps, schema_editor):
    Evaluation = apps.get_model("evaluations", "Evaluation")
    for ev in Evaluation.objects.all():
        ev.uuid = uuid.uuid4()
        ev.save(update_fields=["uuid"])


class Migration(migrations.Migration):

    dependencies = [
        ("evaluations", "0004_catalogue_objectifs_par_defaut"),
    ]

    operations = [
        # 1) Ajout du champ uuid en nullable (pas encore unique) pour pouvoir remplir
        migrations.AddField(
            model_name="evaluation",
            name="uuid",
            field=models.UUIDField(null=True, editable=False),
        ),
        # 2) Remplit un UUID v4 unique pour chaque évaluation existante
        migrations.RunPython(fill_uuids, migrations.RunPython.noop),
        # 3) Verrouille : non nullable + unique + index, avec callable de défaut pour les futures lignes
        migrations.AlterField(
            model_name="evaluation",
            name="uuid",
            field=models.UUIDField(
                default=uuid.uuid4, editable=False, unique=True, db_index=True
            ),
        ),
    ]
