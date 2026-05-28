# Refonte : retrait de Campagne, ajout de date_evaluation et du catalogue d'objectifs.
import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from decimal import Decimal
from django.db import migrations, models


def copier_dates_campagne(apps, schema_editor):
    Evaluation = apps.get_model("evaluations", "Evaluation")
    for ev in Evaluation.objects.all():
        cp = getattr(ev, "campagne", None)
        if cp and cp.date_debut:
            ev.date_evaluation = cp.date_debut
            ev.save(update_fields=["date_evaluation"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("evaluations", "0002_bareme_par_defaut"),
    ]

    operations = [
        # 1) Nouveau champ date_evaluation, rempli par défaut avec maintenant
        migrations.AddField(
            model_name="evaluation",
            name="date_evaluation",
            field=models.DateField(default=django.utils.timezone.now, verbose_name="Date de l'évaluation"),
        ),
        # 2) Récupérer la date depuis la campagne avant de supprimer la FK
        migrations.RunPython(copier_dates_campagne, noop),

        # 3) Catalogue des objectifs
        migrations.CreateModel(
            name="ObjectifCatalogue",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("titre", models.CharField(max_length=300, verbose_name="Titre de l'objectif")),
                ("description", models.TextField(verbose_name="Description")),
                ("livrables", models.TextField(blank=True, verbose_name="Livrables attendus")),
                ("coefficient", models.DecimalField(decimal_places=2, default=Decimal("1"), max_digits=5, validators=[django.core.validators.MinValueValidator(0)], verbose_name="Coefficient (pondération par défaut)")),
                ("ordre", models.PositiveIntegerField(default=0, verbose_name="Ordre d'affichage")),
                ("actif", models.BooleanField(default=True, verbose_name="Actif")),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Objectif (catalogue)",
                "verbose_name_plural": "Catalogue des objectifs",
                "ordering": ["ordre", "id"],
            },
        ),

        # 4) Champs supplémentaires sur Objectif
        migrations.AddField(
            model_name="objectif",
            name="titre",
            field=models.CharField(blank=True, max_length=300, verbose_name="Titre"),
        ),
        migrations.AlterField(
            model_name="objectif",
            name="coefficient",
            field=models.DecimalField(decimal_places=2, default=Decimal("1"), max_digits=5, validators=[django.core.validators.MinValueValidator(0)], verbose_name="Coefficient"),
        ),
        migrations.AlterField(
            model_name="objectif",
            name="taux_atteinte",
            field=models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=5, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)], verbose_name="Taux d'atteinte (%)"),
        ),
        migrations.AddField(
            model_name="objectif",
            name="catalogue",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="utilisations", to="evaluations.objectifcatalogue"),
        ),

        # 5) Retrait de Campagne
        migrations.RemoveConstraint(
            model_name="evaluation",
            name="unique_evaluation_par_campagne",
        ),
        migrations.RemoveField(
            model_name="evaluation",
            name="campagne",
        ),
        migrations.DeleteModel(
            name="Campagne",
        ),

        # 6) Méta options
        migrations.AlterModelOptions(
            name="evaluation",
            options={"ordering": ["-date_evaluation", "-id"], "verbose_name": "Évaluation", "verbose_name_plural": "Évaluations"},
        ),
    ]
