"""Ajoute un UUID public sur Collaborateur, comme pour Evaluation."""
import uuid

from django.db import migrations, models


def fill_uuids(apps, schema_editor):
    Collaborateur = apps.get_model("evaluations", "Collaborateur")
    for c in Collaborateur.objects.all():
        c.uuid = uuid.uuid4()
        c.save(update_fields=["uuid"])


class Migration(migrations.Migration):

    dependencies = [
        ("evaluations", "0005_evaluation_uuid"),
    ]

    operations = [
        migrations.AddField(
            model_name="collaborateur",
            name="uuid",
            field=models.UUIDField(null=True, editable=False),
        ),
        migrations.RunPython(fill_uuids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="collaborateur",
            name="uuid",
            field=models.UUIDField(
                default=uuid.uuid4, editable=False, unique=True, db_index=True
            ),
        ),
    ]
