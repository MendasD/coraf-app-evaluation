from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory

from .models import Collaborateur, Evaluation, NiveauAppreciation, Objectif, ObjectifCatalogue

User = get_user_model()

INPUT = "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 placeholder-slate-400 transition focus:border-coraf-500 focus:ring-2 focus:ring-coraf-100 outline-none"
TEXTAREA = INPUT + " min-h-[72px]"
SELECT = INPUT

# Style pour les champs en lecture seule (verrouillés)
LOCKED_INPUT = (
    "w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm "
    "text-slate-600 cursor-not-allowed"
)
LOCKED_TEXTAREA = LOCKED_INPUT + " min-h-[56px]"


class CollaborateurForm(forms.ModelForm):
    """Création/édition d'un collaborateur.

    À la création, un compte utilisateur peut être généré pour lui permettre
    de se connecter et de remplir ses parties de l'évaluation (faits marquants,
    initiatives personnelles, commentaires).
    """

    creer_compte = forms.BooleanField(
        label="Créer un compte d'accès pour ce collaborateur",
        required=False,
        help_text="L'évalué pourra se connecter et remplir ses parties dans chaque évaluation.",
    )
    compte_email = forms.EmailField(
        label="Adresse email du compte",
        required=False,
        widget=forms.EmailInput(attrs={"class": INPUT, "autocomplete": "off"}),
    )
    compte_password = forms.CharField(
        label="Mot de passe provisoire",
        required=False,
        widget=forms.TextInput(attrs={"class": INPUT, "autocomplete": "new-password"}),
        help_text="Communiquez-le à la personne ; elle pourra le changer après connexion.",
    )

    class Meta:
        model = Collaborateur
        fields = ["nom", "prenom", "type", "poste", "direction", "projets", "date_entree", "actif"]
        widgets = {
            "nom": forms.TextInput(attrs={"class": INPUT}),
            "prenom": forms.TextInput(attrs={"class": INPUT}),
            "type": forms.Select(attrs={"class": SELECT}),
            "poste": forms.TextInput(attrs={"class": INPUT}),
            "direction": forms.TextInput(attrs={"class": INPUT}),
            "projets": forms.TextInput(attrs={"class": INPUT}),
            "date_entree": forms.DateInput(attrs={"class": INPUT, "type": "date"}),
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("creer_compte"):
            email = (cleaned.get("compte_email") or "").strip().lower()
            password = cleaned.get("compte_password")
            if not email:
                self.add_error("compte_email", "L'adresse email est requise pour créer le compte.")
            elif User.objects.filter(email__iexact=email).exists():
                self.add_error("compte_email", "Cette adresse email est déjà utilisée.")
            if not password:
                self.add_error("compte_password", "Le mot de passe provisoire est requis.")
        return cleaned

    def save(self, commit=True):
        collab = super().save(commit=commit)
        if self.cleaned_data.get("creer_compte"):
            email = self.cleaned_data["compte_email"].strip().lower()
            password = self.cleaned_data["compte_password"]
            user = User(
                username=email, email=email,
                first_name=collab.prenom, last_name=collab.nom,
                is_staff=False, is_active=True,
            )
            user.set_password(password)
            user.save()
            collab.user = user
            collab.save(update_fields=["user"])
        return collab


class EvaluationForm(forms.ModelForm):
    """Formulaire côté évaluateur.

    Les champs remplis par l'évalué (faits marquants, initiatives personnelles)
    sont affichés en lecture seule : l'évaluateur peut consulter ce que
    l'évalué a renseigné, mais ne peut pas le modifier.

    Le statut n'est volontairement pas dans ce formulaire : il est pilote par
    les boutons d'action (Soumettre, Valider, Apposer le visa) sur la fiche.
    Une nouvelle évaluation démarre toujours en « Brouillon ».
    """

    class Meta:
        model = Evaluation
        fields = [
            "collaborateur",
            "date_evaluation",
            "responsable_hierarchique",
            "evaluateur",
            "faits_marquants",
            "initiatives_personnelles",
            "points_satisfaction",
            "points_amelioration",
            "propositions_evaluateur",
        ]
        widgets = {
            "collaborateur": forms.Select(attrs={"class": SELECT}),
            "date_evaluation": forms.DateInput(attrs={"class": INPUT, "type": "date"}),
            "responsable_hierarchique": forms.TextInput(attrs={"class": INPUT}),
            "evaluateur": forms.TextInput(attrs={"class": INPUT}),
            "faits_marquants": forms.Textarea(attrs={
                "class": LOCKED_TEXTAREA, "rows": 3,
                "readonly": "readonly", "tabindex": "-1",
                "placeholder": "Cette section est remplie par l'évalué depuis son espace.",
            }),
            "initiatives_personnelles": forms.Textarea(attrs={
                "class": LOCKED_TEXTAREA, "rows": 3,
                "readonly": "readonly", "tabindex": "-1",
                "placeholder": "Cette section est remplie par l'évalué depuis son espace.",
            }),
            "points_satisfaction": forms.Textarea(attrs={"class": TEXTAREA}),
            "points_amelioration": forms.Textarea(attrs={"class": TEXTAREA}),
            "propositions_evaluateur": forms.Textarea(attrs={"class": TEXTAREA}),
        }


class EvaluationEvalueForm(forms.ModelForm):
    """Formulaire restreint réservé à l'évalué : seules les sections qui le
    concernent sont éditables."""

    class Meta:
        model = Evaluation
        fields = ["faits_marquants", "initiatives_personnelles"]
        widgets = {
            "faits_marquants": forms.Textarea(attrs={"class": TEXTAREA, "rows": 4}),
            "initiatives_personnelles": forms.Textarea(attrs={"class": TEXTAREA, "rows": 4}),
        }


class ObjectifCommentaireEvalueForm(forms.ModelForm):
    """Formulaire d'un objectif vu par l'évalué : seul le commentaire de
    l'évalué est éditable, le reste est en lecture seule."""

    class Meta:
        model = Objectif
        fields = ["commentaire_evalue"]
        widgets = {
            "commentaire_evalue": forms.Textarea(attrs={"class": TEXTAREA, "rows": 2}),
        }


ObjectifCommentaireEvalueFormSet = inlineformset_factory(
    Evaluation,
    Objectif,
    form=ObjectifCommentaireEvalueForm,
    extra=0,
    can_delete=False,
)


class ObjectifForm(forms.ModelForm):
    """Formulaire d'objectif dans une évaluation.

    Les champs venant du catalogue (numéro, titre, description, livrables,
    coefficient) sont en lecture seule : l'évaluateur ne peut modifier que le
    taux d'atteinte et les commentaires.
    """

    class Meta:
        model = Objectif
        fields = [
            "numero",
            "titre",
            "description",
            "livrables",
            "coefficient",
            "taux_atteinte",
            "commentaire_evalue",
            "commentaire_evaluateur",
        ]
        widgets = {
            "numero": forms.NumberInput(attrs={
                "class": LOCKED_INPUT + " w-16 text-center",
                "readonly": "readonly", "tabindex": "-1",
            }),
            "titre": forms.TextInput(attrs={
                "class": LOCKED_INPUT,
                "readonly": "readonly", "tabindex": "-1",
            }),
            "description": forms.Textarea(attrs={
                "class": LOCKED_TEXTAREA, "rows": 2,
                "readonly": "readonly", "tabindex": "-1",
            }),
            "livrables": forms.Textarea(attrs={
                "class": LOCKED_TEXTAREA, "rows": 2,
                "readonly": "readonly", "tabindex": "-1",
            }),
            "coefficient": forms.NumberInput(attrs={
                "class": LOCKED_INPUT + " coef-input w-24 text-center",
                "readonly": "readonly", "tabindex": "-1",
            }),
            "taux_atteinte": forms.NumberInput(
                attrs={"class": INPUT + " taux-input", "step": "1", "min": 0, "max": 100}
            ),
            "commentaire_evalue": forms.Textarea(attrs={
                "class": LOCKED_TEXTAREA, "rows": 2,
                "readonly": "readonly", "tabindex": "-1",
                "placeholder": "Commentaire de l'évalué (rempli par l'intéressé).",
            }),
            "commentaire_evaluateur": forms.Textarea(attrs={"class": TEXTAREA, "rows": 2}),
        }


ObjectifFormSet = inlineformset_factory(
    Evaluation,
    Objectif,
    form=ObjectifForm,
    extra=0,
    can_delete=True,
)


class ObjectifCatalogueForm(forms.ModelForm):
    class Meta:
        model = ObjectifCatalogue
        fields = ["titre", "description", "livrables", "coefficient", "ordre", "actif"]
        widgets = {
            "titre": forms.TextInput(attrs={"class": INPUT}),
            "description": forms.Textarea(attrs={"class": TEXTAREA, "rows": 3}),
            "livrables": forms.Textarea(attrs={"class": TEXTAREA, "rows": 2}),
            "coefficient": forms.NumberInput(attrs={"class": INPUT, "step": "0.5", "min": 0}),
            "ordre": forms.NumberInput(attrs={"class": INPUT, "min": 0}),
        }


class NiveauAppreciationForm(forms.ModelForm):
    class Meta:
        model = NiveauAppreciation
        fields = ["libelle", "seuil_min", "seuil_max", "couleur"]
        widgets = {
            "libelle": forms.TextInput(attrs={"class": INPUT}),
            "seuil_min": forms.NumberInput(attrs={"class": INPUT, "step": "0.01", "min": 0, "max": 100}),
            "seuil_max": forms.NumberInput(attrs={"class": INPUT, "step": "0.01", "min": 0, "max": 100}),
            "couleur": forms.TextInput(attrs={"class": INPUT, "type": "color"}),
        }


class EmailAuthenticationForm(AuthenticationForm):
    """Connexion par email · le champ 'username' reste l'identifiant
    interne pour Django mais on l'affiche en tant qu'email."""

    username = forms.EmailField(
        label="Adresse email",
        widget=forms.EmailInput(attrs={
            "class": INPUT,
            "autocomplete": "email",
            "autofocus": True,
            "placeholder": "vous@coraf.org",
        }),
    )


class UtilisateurCreationForm(forms.ModelForm):
    """Formulaire admin pour créer un compte évaluateur (ou évaluateur-admin).

    L'identifiant `username` n'est pas exposé : il est généré
    automatiquement à partir de l'email.
    """

    password1 = forms.CharField(
        label="Mot de passe provisoire",
        widget=forms.TextInput(attrs={"class": INPUT, "autocomplete": "new-password"}),
        help_text="Communiquez-le à la personne ; elle pourra le changer après connexion.",
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "is_staff", "is_active"]
        labels = {
            "first_name": "Prénom",
            "last_name": "Nom",
            "email": "Adresse email",
            "is_staff": "Privilèges administrateur",
            "is_active": "Compte actif",
        }
        widgets = {
            "first_name": forms.TextInput(attrs={"class": INPUT}),
            "last_name": forms.TextInput(attrs={"class": INPUT}),
            "email": forms.EmailInput(attrs={"class": INPUT, "autocomplete": "off"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Nom et prénom obligatoires : ils servent au pré-remplissage de
        # l'évaluateur et à l'affichage humain partout dans l'app.
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if not email:
            raise ValidationError("L'adresse email est obligatoire.")
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("Cette adresse email est déjà utilisée par un autre compte.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        email = self.cleaned_data["email"]
        # On utilise l'email comme username interne (Django l'exige).
        # En cas de collision (théorique, déjà bloquée par clean_email), on suffixe.
        base = email
        username = base
        idx = 1
        while User.objects.filter(username=username).exclude(pk=user.pk).exists():
            idx += 1
            username = f"{base}#{idx}"
        user.username = username
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class UtilisateurEditForm(forms.ModelForm):
    """Édition d'un compte existant (sans toucher au mot de passe).
    Modifier l'email re-synchronise le `username` interne.
    """

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "is_staff", "is_active"]
        labels = {
            "first_name": "Prénom",
            "last_name": "Nom",
            "email": "Adresse email",
            "is_staff": "Privilèges administrateur",
            "is_active": "Compte actif",
        }
        widgets = {
            "first_name": forms.TextInput(attrs={"class": INPUT}),
            "last_name": forms.TextInput(attrs={"class": INPUT}),
            "email": forms.EmailInput(attrs={"class": INPUT}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if not email:
            raise ValidationError("L'adresse email est obligatoire.")
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise ValidationError("Cette adresse email est déjà utilisée par un autre compte.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


class UtilisateurResetPasswordForm(forms.Form):
    password = forms.CharField(
        label="Nouveau mot de passe provisoire",
        widget=forms.TextInput(attrs={"class": INPUT, "autocomplete": "new-password"}),
    )

