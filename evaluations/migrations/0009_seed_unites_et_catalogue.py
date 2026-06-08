"""Crée les 8 unités CORAF et seed les objectifs catalogue par unité.

- L'unité KM hérite des 5 objectifs catalogue existants (POKO Alida).
- Les unités M&E, Genre et Gestionnaire de Projet sont seedées depuis les
  formulaires officiels fournis.
- Les autres unités (Comptable, Passations de Marchés, Environnement,
  Ressource Humaine) sont créées sans objectifs ; l'admin les ajoutera
  manuellement via l'interface.
- Tous les coefficients sont à 1 (pondération égalitaire) ; l'admin ajustera.
"""
from decimal import Decimal
from django.db import migrations

UNITES = [
    ("KM", "KM", "Gestion des connaissances (Knowledge Management)"),
    ("ME", "M&E", "Suivi-Évaluation (Monitoring & Evaluation)"),
    ("GPP", "Gestionnaire de Projet et Programme", "Coordination et gestion de projets et programmes"),
    ("COMPTA", "Comptable", "Comptabilité et gestion financière"),
    ("MARCHES", "Passations de Marchés", "Passation des marchés et achats"),
    ("GENRE", "Genre", "Genre et développement social"),
    ("ENV", "Environnement", "Sauvegarde environnementale"),
    ("RH", "Ressource Humaine", "Ressources humaines"),
]

OBJECTIFS_ME = [
    (
        "Définir et mettre en place un système Suivi-Évaluation performant",
        "Définir et mettre en place un système Suivi-Évaluation performant au CORAF.",
        "Définir et proposer les outils du système Suivi-Évaluation (procédures, fiches, formulaires, indicateurs) : plan de collecte, plan d'analyse, plan d'utilisation des données.",
    ),
    (
        "Mettre en œuvre et animer le système Suivi-Évaluation",
        "Mettre en œuvre et animer le système Suivi-Évaluation.",
        "Préparer les fiches de référence des indicateurs, les plans de suivi des performances (PMP), les outils de collecte de données, les évaluations de la qualité des données.",
    ),
    (
        "Effectuer toute activité ou tâche en lien avec ses missions",
        "Effectuer toute activité ou tâche en lien avec ses missions sur demande.",
        "Appuyer le cadre institutionnel de suivi évaluation du CORAF (DIP 4).",
    ),
]

OBJECTIFS_GENRE = [
    (
        "Définir et mettre en place un système Genre",
        "Définir et mettre en place un système performant en matière de genre et de développement social au CORAF.",
        "Élaborer ou proposer la politique genre du CORAF ; définir et mettre en place les outils (procédures, fiches, indicateurs).",
    ),
    (
        "Animer la veille genre et développement social",
        "Mettre en place, organiser et animer la veille en matière de genre et de développement social au CORAF.",
        "Définir et organiser le système de veille ; effectuer une veille active sur les évolutions susceptibles d'impacter le secteur.",
    ),
    (
        "Participer à la stratégie globale du CORAF",
        "Participer à la conception de la stratégie globale du CORAF.",
        "Alimenter la réflexion stratégique avec les résultats de la veille genre.",
    ),
    (
        "Coordonner les aspects genre dans les projets",
        "Coordonner les aspects genre dans les projets et programmes.",
        "Appuyer les pays et les institutions régionales pour la prise en compte du genre dans l'exécution des programmes.",
    ),
    (
        "Coordonner les aspects genre dans le projet FSRP",
        "Coordonner les aspects genre dans le projet FSRP.",
        "Intégrer les aspects genre dans le cycle du projet FSRP ; appuyer les pays et institutions partenaires.",
    ),
    (
        "Développer des collaborations et partenariats Genre",
        "Développer des collaborations et partenariats dans le domaine du Genre.",
        "Identifier et développer des partenariats stratégiques avec les réseaux de connaissances, les SNRA et les partenaires régionaux.",
    ),
    (
        "Représenter le CORAF dans les instances genre",
        "Représenter le CORAF dans les instances et événements en matière genre.",
        "Représenter le CORAF aux foires agricoles internationales et instances traitant les thématiques genre.",
    ),
    (
        "Participer au système Knowledge Management",
        "Participer à la mise en place et à l'œuvre du système de Knowledge Management (KM).",
        "Contribuer au diagnostic et à la formalisation des connaissances du CORAF en lien avec le genre.",
    ),
    (
        "Superviser les Chargés / Assistants genre",
        "Superviser les Chargés et Assistants genre.",
        "Organiser le travail, fixer les objectifs et assurer la répartition optimale des activités de l'équipe genre.",
    ),
    (
        "Effectuer toute activité en lien avec ses missions",
        "Effectuer toute activité ou tâche en lien avec ses missions sur demande.",
        "Notamment la mise en œuvre du projet PYD.",
    ),
]

OBJECTIFS_GPP = [
    (
        "Coordonner la mise en œuvre effective des projets",
        "Coordonner la mise en œuvre effective des projets conformément aux objectifs fixés.",
        "Bonne exécution technique et financière des activités par l'ensemble des partenaires de mise en œuvre.",
    ),
    (
        "Suivre régulièrement la mise en œuvre des activités",
        "Suivre régulièrement la mise en œuvre des activités et s'assurer qu'elles s'exécutent conformément au plan de travail.",
        "Renseigner les indicateurs qui conditionnent l'atteinte des objectifs.",
    ),
    (
        "Coordonner l'organisation des réunions et ateliers",
        "Coordonner l'organisation des réunions et ateliers.",
        "Tenir les rencontres des projets dans de bonnes conditions afin d'atteindre les objectifs.",
    ),
    (
        "Assurer l'interface au sein du Secrétariat Exécutif",
        "Assurer l'interface, au niveau du Secrétariat Exécutif du CORAF, entre le demandeur principal et les codemandeurs.",
        "Servir de courroie de transmission entre les partenaires du projet.",
    ),
    (
        "Présider les rencontres avec les institutions partenaires",
        "Présider les rencontres avec les responsables des projets dans les institutions partenaires.",
        "Avoir des rencontres fructueuses pour lesquelles les objectifs sont atteints.",
    ),
    (
        "Préparer les documents de contractualisation",
        "Préparer les documents de contractualisation avec les codemandeurs.",
        "Contrats bien libellés et acceptés par toutes les parties.",
    ),
    (
        "Répondre aux sollicitations des bailleurs",
        "Répondre à toute sollicitation émanant du Chargé de Programme Agriculture et Développement Rural et de la DUE / DEVCO.",
        "Permettre aux partenaires financiers de statuer sur les décisions à prendre.",
    ),
    (
        "Proposer des projets aux bailleurs",
        "Proposer des projets à soumettre aux bailleurs.",
        "Augmenter le portefeuille de projets du CORAF et ses ressources financières.",
    ),
    (
        "Mobiliser des ressources additionnelles",
        "Assurer la mobilisation de ressources additionnelles pour le CORAF.",
        "Permettre au CORAF de disposer de ressources financières pour la mise en œuvre du Plan Opérationnel 2023-2027.",
    ),
]


def seed(apps, schema_editor):
    Unite = apps.get_model("evaluations", "Unite")
    ObjectifCatalogue = apps.get_model("evaluations", "ObjectifCatalogue")
    Collaborateur = apps.get_model("evaluations", "Collaborateur")

    # 1. Création des 8 unités
    unites_par_code = {}
    for idx, (code, libelle, description) in enumerate(UNITES, start=1):
        u, _ = Unite.objects.get_or_create(
            code=code,
            defaults={"libelle": libelle, "description": description, "ordre": idx},
        )
        unites_par_code[code] = u

    # 2. Réaffectation des objectifs catalogue existants (5 KM de POKO) à l'unité KM
    km = unites_par_code["KM"]
    for cat in ObjectifCatalogue.objects.filter(unite__isnull=True):
        cat.unite = km
        cat.coefficient = Decimal("1")  # pondération égalitaire
        cat.save(update_fields=["unite", "coefficient"])

    # 3. Seed des objectifs des unités M&E, Genre et GPP (coef = 1 pour tous)
    def seed_unite(unite, objs):
        for idx, (titre, description, livrables) in enumerate(objs, start=1):
            ObjectifCatalogue.objects.get_or_create(
                unite=unite,
                titre=titre,
                defaults={
                    "description": description,
                    "livrables": livrables,
                    "coefficient": Decimal("1"),
                    "ordre": idx,
                    "actif": True,
                },
            )

    seed_unite(unites_par_code["ME"], OBJECTIFS_ME)
    seed_unite(unites_par_code["GENRE"], OBJECTIFS_GENRE)
    seed_unite(unites_par_code["GPP"], OBJECTIFS_GPP)

    # 4. Affecter les collaborateurs existants à l'unité KM par défaut
    #    (la collaboratrice de seed POKO + tests éventuels)
    Collaborateur.objects.filter(unite__isnull=True).update(unite=km)


def unseed(apps, schema_editor):
    Unite = apps.get_model("evaluations", "Unite")
    ObjectifCatalogue = apps.get_model("evaluations", "ObjectifCatalogue")
    Collaborateur = apps.get_model("evaluations", "Collaborateur")
    Collaborateur.objects.update(unite=None)
    ObjectifCatalogue.objects.filter(unite__code__in=["ME", "GENRE", "GPP"]).delete()
    ObjectifCatalogue.objects.update(unite=None)
    Unite.objects.filter(code__in=[c for c, _, _ in UNITES]).delete()


class Migration(migrations.Migration):
    dependencies = [("evaluations", "0008_unite_alter_objectifcatalogue_options_and_more")]
    operations = [migrations.RunPython(seed, unseed)]
