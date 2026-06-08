import uuid as uuid_lib
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone


class Unite(models.Model):
    """Unité fonctionnelle CORAF (KM, M&E, Genre, etc.).

    Les objectifs et les évaluations sont rattachés à une unité : un évalué
    voit uniquement les objectifs prédéfinis pour SON unité.
    """

    code = models.SlugField("Code", max_length=40, unique=True)
    libelle = models.CharField("Libellé", max_length=120)
    description = models.TextField("Description", blank=True)
    ordre = models.PositiveIntegerField("Ordre d'affichage", default=0)
    actif = models.BooleanField("Active", default=True)

    class Meta:
        verbose_name = "Unité"
        verbose_name_plural = "Unités"
        ordering = ["ordre", "libelle"]

    def __str__(self):
        return self.libelle


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
    # L'évaluateur attitré du collaborateur : c'est lui qui revoit, valide et
    # signe l'évaluation envoyée par l'évalué.
    evaluateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="collaborateurs_a_evaluer",
        verbose_name="Évaluateur attitré",
    )
    # Unité d'affectation (détermine la grille d'objectifs).
    unite = models.ForeignKey(
        Unite,
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name="collaborateurs",
        verbose_name="Unité",
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

    unite = models.ForeignKey(
        Unite,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="objectifs_catalogue",
        verbose_name="Unité",
        help_text="Les évalués de cette unité auront cet objectif dans leur évaluation.",
    )
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
        ordering = ["unite__ordre", "ordre", "id"]

    def __str__(self):
        suffix = f" [{self.unite.libelle}]" if self.unite_id else ""
        return f"{self.titre}{suffix}"


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
        """Crée les Objectifs de l'évaluation depuis le catalogue de l'unité du collaborateur.

        Si le collaborateur n'a pas d'unité, ne crée rien (l'admin devra
        intervenir pour ajouter manuellement des objectifs).
        """
        if self.objectifs.exists():
            return
        unite = self.collaborateur.unite
        if not unite:
            return
        for idx, cat in enumerate(
            ObjectifCatalogue.objects.filter(unite=unite, actif=True).order_by("ordre", "id"),
            start=1,
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


class FaitMarquant(models.Model):
    """Un fait marquant saisi par l'évalué (avec son observation associée).

    Présenté en tableau dans la fiche papier officielle (numéro, fait, observation).
    """

    evaluation = models.ForeignKey(
        Evaluation, on_delete=models.CASCADE, related_name="faits_marquants_lignes"
    )
    ordre = models.PositiveIntegerField("N°", default=1)
    fait = models.TextField("Fait marquant", blank=True)
    observation = models.TextField("Observations", blank=True)

    class Meta:
        verbose_name = "Fait marquant"
        verbose_name_plural = "Faits marquants"
        ordering = ["ordre", "id"]

    def __str__(self):
        return f"Fait {self.ordre} de {self.evaluation_id}"


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


class UserPreference(models.Model):
    """Préférences utilisateur (un par User).

    Stocke notamment le timestamp à partir duquel l'utilisateur souhaite voir
    son journal d'audit. Les logs antérieurs restent en base (audit
    administrateur) mais n'apparaissent plus dans sa vue personnelle.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="preferences",
    )
    audit_cleared_at = models.DateTimeField(
        "Logs vidés jusqu'à",
        null=True, blank=True,
    )

    class Meta:
        verbose_name = "Préférences utilisateur"
        verbose_name_plural = "Préférences utilisateurs"

    def __str__(self):
        return f"Préférences de {self.user}"


class AuditLog(models.Model):
    """Journal des actions menées sur la plateforme.

    Les admins voient tous les logs ; les non-admins ne voient que les logs où
    ils sont l'acteur OU la cible (cas typique : un admin reset leur mdp).
    """

    class Action(models.TextChoices):
        CREATE = "CREATE", "Création"
        UPDATE = "UPDATE", "Modification"
        DELETE = "DELETE", "Suppression"
        LOGIN = "LOGIN", "Connexion"
        STATUT = "STATUT", "Changement de statut"
        PASSWORD = "PASSWORD", "Mot de passe modifié"
        OTHER = "OTHER", "Action"

    date = models.DateTimeField("Date", default=timezone.now, db_index=True)
    acteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="audit_logs_emis",
        verbose_name="Acteur",
    )
    # Utilisateur cible (si l'action concerne directement un user, ex. reset password)
    cible_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="audit_logs_recus",
        verbose_name="Utilisateur ciblé",
    )
    action = models.CharField("Action", max_length=20, choices=Action.choices)
    modele = models.CharField("Modèle concerné", max_length=80, blank=True)
    objet_id = models.CharField("Identifiant de l'objet", max_length=80, blank=True)
    description = models.CharField("Description", max_length=300)

    class Meta:
        verbose_name = "Entrée d'audit"
        verbose_name_plural = "Journal d'audit"
        ordering = ["-date", "-id"]

    def __str__(self):
        who = self.acteur.get_full_name() if self.acteur else "Système"
        return f"{self.date:%d/%m/%Y %H:%M} · {who} · {self.get_action_display()} · {self.description}"

    @classmethod
    def log(cls, acteur, action, description, *, modele="", objet_id="", cible_user=None):
        """Helper pour créer un log en une ligne depuis les vues."""
        return cls.objects.create(
            acteur=acteur if (acteur and getattr(acteur, "is_authenticated", False)) else None,
            action=action,
            description=description[:300],
            modele=modele,
            objet_id=str(objet_id) if objet_id else "",
            cible_user=cible_user,
        )
