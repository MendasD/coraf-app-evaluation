import uuid as uuid_lib
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone


class Collaborateur(models.Model):
    class Type(models.TextChoices):
        CONSULTANT = "CONSULTANT", "Consultant interne"
        STAGIAIRE = "STAGIAIRE", "Stagiaire"
        EMPLOYE = "EMPLOYE", "Employé"

    # Identifiant public pour les URLs (le pk auto reste pour les FK internes).
    uuid = models.UUIDField(
        default=uuid_lib.uuid4, editable=False, unique=True, db_index=True
    )
    # Compte utilisateur lié pour que l'évalué se connecte et remplisse ses parties.
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="profil_collaborateur",
        verbose_name="Compte utilisateur lié",
    )
    nom = models.CharField("Nom", max_length=120)
    prenom = models.CharField("Prénom", max_length=120, blank=True)
    type = models.CharField("Type", max_length=20, choices=Type.choices, default=Type.EMPLOYE)
    poste = models.CharField("Intitulé du poste", max_length=200, blank=True)
    direction = models.CharField("Direction", max_length=200, blank=True)
    projets = models.CharField("Projets", max_length=300, blank=True)
    date_entree = models.DateField("Date d'entrée", null=True, blank=True)
    actif = models.BooleanField("Actif", default=True)

    class Meta:
        verbose_name = "Collaborateur"
        verbose_name_plural = "Collaborateurs"
        ordering = ["nom", "prenom"]

    def __str__(self):
        return f"{self.nom} {self.prenom}".strip()

    @property
    def nom_complet(self):
        return f"{self.nom} {self.prenom}".strip()

    def get_absolute_url(self):
        return reverse("evaluations:collaborateur_detail", args=[self.uuid])


class NiveauAppreciation(models.Model):
    """Barème paramétrable : une bande de note globale (en %) -> un libellé."""

    libelle = models.CharField("Appréciation", max_length=100)
    seuil_min = models.DecimalField(
        "Seuil min (%)", max_digits=5, decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    seuil_max = models.DecimalField(
        "Seuil max (%)", max_digits=5, decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    couleur = models.CharField(
        "Couleur (hex)", max_length=7, default="#64748b",
        help_text="Ex. #16a34a",
    )

    class Meta:
        verbose_name = "Niveau d'appréciation"
        verbose_name_plural = "Barème d'appréciation"
        ordering = ["-seuil_min"]

    def __str__(self):
        return f"{self.libelle} ({self.seuil_min}–{self.seuil_max} %)"

    @classmethod
    def pour_note(cls, note_pct):
        if note_pct is None:
            return None
        return (
            cls.objects.filter(seuil_min__lte=note_pct, seuil_max__gte=note_pct)
            .order_by("-seuil_min")
            .first()
        )


class ObjectifCatalogue(models.Model):
    """Catalogue maître des objectifs d'évaluation gérés par l'administration.

    Chaque nouvelle évaluation est pré-remplie avec les objectifs actifs du
    catalogue. Les administrateurs peuvent en ajouter, désactiver ou
    réajuster les coefficients sans modifier l'historique des évaluations
    déjà saisies (les objectifs d'une évaluation gardent leurs propres
    valeurs au moment de la saisie).
    """

    titre = models.CharField("Titre de l'objectif", max_length=300)
    description = models.TextField("Description")
    livrables = models.TextField("Livrables attendus", blank=True)
    coefficient = models.DecimalField(
        "Coefficient (pondération par défaut)",
        max_digits=5, decimal_places=2, default=Decimal("1"),
        validators=[MinValueValidator(0)],
    )
    ordre = models.PositiveIntegerField("Ordre d'affichage", default=0)
    actif = models.BooleanField("Actif", default=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Objectif (catalogue)"
        verbose_name_plural = "Catalogue des objectifs"
        ordering = ["ordre", "id"]

    def __str__(self):
        return self.titre


class Evaluation(models.Model):
    class Statut(models.TextChoices):
        BROUILLON = "BROUILLON", "Brouillon"
        SOUMISE = "SOUMISE", "Soumise"
        VALIDEE = "VALIDEE", "Validée"
        VISEE_RH = "VISEE_RH", "Visée RH"

    # Identifiant public (utilisé dans les URLs) pour ne pas exposer le compteur séquentiel.
    uuid = models.UUIDField(
        default=uuid_lib.uuid4, editable=False, unique=True, db_index=True
    )

    collaborateur = models.ForeignKey(
        Collaborateur, on_delete=models.CASCADE, related_name="evaluations"
    )
    date_evaluation = models.DateField("Date de l'évaluation", default=timezone.now)

    responsable_hierarchique = models.CharField(
        "Responsable hiérarchique / point focal", max_length=200, blank=True
    )
    evaluateur = models.CharField("Évaluateur", max_length=200, blank=True)

    # Sections remplies par l'évalué
    faits_marquants = models.TextField("Principaux faits marquants", blank=True)
    initiatives_personnelles = models.TextField("Initiatives personnelles", blank=True)

    # Sections remplies par l'évaluateur
    points_satisfaction = models.TextField("Points de satisfaction", blank=True)
    points_amelioration = models.TextField("Points à améliorer", blank=True)
    propositions_evaluateur = models.TextField(
        "Propositions de l'évaluateur (formation/carrière)", blank=True
    )

    statut = models.CharField(
        "Statut", max_length=20, choices=Statut.choices, default=Statut.BROUILLON
    )

    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Évaluation"
        verbose_name_plural = "Évaluations"
        ordering = ["-date_evaluation", "-id"]

    def __str__(self):
        return f"{self.collaborateur} · {self.date_evaluation:%d/%m/%Y}"

    def get_absolute_url(self):
        return reverse("evaluations:evaluation_detail", args=[self.uuid])

    @property
    def total_coefficient(self):
        return sum((o.coefficient for o in self.objectifs.all()), Decimal("0"))

    @property
    def total_note(self):
        return sum((o.note for o in self.objectifs.all()), Decimal("0"))

    @property
    def note_globale(self):
        """Taux d'exécution globale en % = Σ(coef×taux) / Σ(coef)."""
        total_coef = self.total_coefficient
        if not total_coef:
            return None
        return (self.total_note / total_coef * Decimal("100")).quantize(Decimal("0.01"))

    @property
    def appreciation(self):
        return NiveauAppreciation.pour_note(self.note_globale)

    # --- Permissions de modification ---------------------------------------

    def est_evalue(self, user):
        """L'utilisateur est-il l'évalué de cette évaluation ?"""
        return (
            user is not None
            and user.is_authenticated
            and self.collaborateur.user_id == user.id
        )

    def peut_etre_modifie_par_evalue(self):
        """L'évalué ne peut modifier que tant que l'évaluation est en brouillon."""
        return self.statut == self.Statut.BROUILLON

    def peut_etre_modifie_par_evaluateur(self):
        """L'évaluateur peut modifier tant que ce n'est pas visé RH."""
        return self.statut != self.Statut.VISEE_RH

    def remplir_objectifs_depuis_catalogue(self):
        """Crée les Objectifs de l'évaluation depuis les objectifs actifs du catalogue."""
        if self.objectifs.exists():
            return
        for idx, cat in enumerate(
            ObjectifCatalogue.objects.filter(actif=True).order_by("ordre", "id"), start=1
        ):
            Objectif.objects.create(
                evaluation=self,
                catalogue=cat,
                numero=idx,
                titre=cat.titre,
                description=cat.description,
                livrables=cat.livrables,
                coefficient=cat.coefficient,
            )


class Objectif(models.Model):
    """Objectif rattaché à une évaluation (snapshot du catalogue au moment de la saisie)."""

    evaluation = models.ForeignKey(
        Evaluation, on_delete=models.CASCADE, related_name="objectifs"
    )
    catalogue = models.ForeignKey(
        ObjectifCatalogue, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="utilisations",
    )

    numero = models.PositiveIntegerField("N°", default=1)
    titre = models.CharField("Titre", max_length=300, blank=True)
    description = models.TextField("Description de l'objectif")
    livrables = models.TextField("Livrables", blank=True)
    coefficient = models.DecimalField(
        "Coefficient", max_digits=5, decimal_places=2, default=Decimal("1"),
        validators=[MinValueValidator(0)],
    )
    taux_atteinte = models.DecimalField(
        "Taux d'atteinte (%)", max_digits=5, decimal_places=2,
        default=Decimal("0"),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    commentaire_evalue = models.TextField("Commentaires de l'évalué", blank=True)
    commentaire_evaluateur = models.TextField("Commentaires de l'évaluateur", blank=True)

    class Meta:
        verbose_name = "Objectif"
        verbose_name_plural = "Objectifs"
        ordering = ["numero", "id"]

    def __str__(self):
        return self.titre or f"Objectif {self.numero}"

    @property
    def note(self):
        return (self.coefficient * self.taux_atteinte / Decimal("100")).quantize(
            Decimal("0.01")
        )
