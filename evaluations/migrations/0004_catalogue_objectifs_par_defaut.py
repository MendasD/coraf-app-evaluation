from decimal import Decimal

from django.db import migrations

OBJECTIFS = [
    {
        "ordre": 1,
        "coefficient": Decimal("5"),
        "titre": "Coordonner la formalisation et la mise en œuvre de la stratégie régionale de gestion des connaissances",
        "description": (
            "Coordonner la formalisation et la mise en œuvre de la stratégie "
            "régionale de gestion des connaissances du CORAF, alignée aux plans "
            "stratégique et opérationnel."
        ),
        "livrables": "Version validée de la stratégie, note de cadrage du plan d'action, réunion de présentation",
    },
    {
        "ordre": 2,
        "coefficient": Decimal("4"),
        "titre": "Développer une infrastructure KM intégrée",
        "description": (
            "Développer une infrastructure KM intégrée pour la préservation, "
            "l'accès et la valorisation des savoirs de l'organisation."
        ),
        "livrables": "Plateformes (DKH, DSpace, MITA, Agripreneur TV) fonctionnelles (v.1), manuel utilisateur, test interne, utilisateurs formés",
    },
    {
        "ordre": 3,
        "coefficient": Decimal("2"),
        "titre": "Structurer et piloter des processus de capitalisation",
        "description": (
            "Structurer et piloter des processus de capitalisation des approches "
            "et innovations du CORAF."
        ),
        "livrables": "Guide validé, modèle de fiche capitalisation, sessions d'appropriation",
    },
    {
        "ordre": 4,
        "coefficient": Decimal("2"),
        "titre": "Favoriser une culture de partage des connaissances",
        "description": (
            "Favoriser une culture de partage des connaissances et apprentissage "
            "organisationnel par l'animation de communautés de pratiques et des "
            "formations ciblées."
        ),
        "livrables": "Atelier réalisé, supports de formation, rapport de synthèse",
    },
    {
        "ordre": 5,
        "coefficient": Decimal("2"),
        "titre": "Produire, documenter et disséminer des produits de connaissances",
        "description": (
            "Produire, documenter et disséminer des produits de connaissances "
            "multiformats valorisant les résultats, les pratiques et l'expertise "
            "du CORAF."
        ),
        "livrables": "Procédures et processus formalisés en ligne (DKH, DSpace), guide de contribution interne, accès partagé",
    },
]


def seed_catalogue(apps, schema_editor):
    Cat = apps.get_model("evaluations", "ObjectifCatalogue")
    if Cat.objects.exists():
        return
    for o in OBJECTIFS:
        Cat.objects.create(**o)


def unseed(apps, schema_editor):
    Cat = apps.get_model("evaluations", "ObjectifCatalogue")
    Cat.objects.filter(titre__in=[o["titre"] for o in OBJECTIFS]).delete()


class Migration(migrations.Migration):
    dependencies = [("evaluations", "0003_objectifcatalogue_remove_evaluation_campagne_and_more")]
    operations = [migrations.RunPython(seed_catalogue, unseed)]
