from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory

from .models import (
    Collaborateur,
    Evaluation,
    FaitMarquant,
    NiveauAppreciation,
    Objectif,
    ObjectifCatalogue,
    Unite,
)

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

    À la création, un compte utilisateur est obligatoirement créé : l'évalué
    se connecte avec et démarre lui-même ses évaluations. L'admin doit aussi
    désigner son évaluateur attitré.
    """

    compte_email = forms.EmailField(
        label="Adresse email du compte",
        widget=forms.EmailInput(attrs={"class": INPUT, "autocomplete": "off"}),
        help_text="Sera utilisée pour se connecter à la plateforme.",
    )
    compte_password = forms.CharField(
        label="Mot de passe provisoire",
        widget=forms.TextInput(attrs={"class": INPUT, "autocomplete": "new-password"}),
        help_text="Communiquez-le à la personne ; elle pourra le changer après connexion.",
        required=False,  # requis seulement à la création (voir __init__)
    )

    class Meta:
        model = Collaborateur
        fields = [
            "nom", "prenom", "type", "unite", "evaluateur",
            "poste", "direction", "projets", "date_entree", "actif",
        ]
        widgets = {
            "nom": forms.TextInput(attrs={"class": INPUT}),
            "prenom": forms.TextInput(attrs={"class": INPUT}),
            "type": forms.Select(attrs={"class": SELECT}),
            "unite": forms.Select(attrs={"class": SELECT}),
            "evaluateur": forms.Select(attrs={"class": SELECT}),
            "poste": forms.TextInput(attrs={"class": INPUT}),
            "direction": forms.TextInput(attrs={"class": INPUT}),
            "projets": forms.TextInput(attrs={"class": INPUT}),
            "date_entree": forms.DateInput(attrs={"class": INPUT, "type": "date"}),
        }
        labels = {
            "unite": "Unité d'affectation",
            "evaluateur": "Évaluateur attitré",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["unite"].required = True
        self.fields["evaluateur"].required = True
        # Choix Évaluateur : on n'expose que les Users qui ne sont pas eux-mêmes des évalués
        # (pour éviter de désigner un évalué comme évaluateur d'un autre par mégarde).
        evaluateur_qs = User.objects.filter(
            is_active=True, profil_collaborateur__isnull=True
        ).order_by("first_name", "last_name", "email")
        self.fields["evaluateur"].queryset = evaluateur_qs
        self.fields["evaluateur"].label_from_instance = lambda u: (
            (u.get_full_name() or u.email) + (" · Admin" if u.is_staff else "")
        )
        # Le compte est obligatoire seulement à la création (pas en édition d'un
        # collaborateur qui a déjà un compte).
        if self.instance.pk and self.instance.user_id:
            self.fields["compte_email"].required = False
            self.fields["compte_password"].required = False
            self.fields["compte_email"].initial = self.instance.user.email
            self.fields["compte_email"].disabled = True
            self.fields["compte_password"].help_text = "Laisser vide pour ne pas changer."
        else:
            self.fields["compte_email"].required = True
            self.fields["compte_password"].required = True

    def clean_compte_email(self):
        email = (self.cleaned_data.get("compte_email") or "").strip().lower()
        if not email:
            return email
        qs = User.objects.filter(email__iexact=email)
        if self.instance.pk and self.instance.user_id:
            qs = qs.exclude(pk=self.instance.user_id)
        if qs.exists():
            raise ValidationError("Cette adresse email est déjà utilisée.")
        return email

    def save(self, commit=True):
        collab = super().save(commit=False)
        email = self.cleaned_data.get("compte_email")
        password = self.cleaned_data.get("compte_password")

        if collab.user_id:
            # Édition : on met à jour first/last du user lié + mot de passe si fourni
            user = collab.user
            user.first_name = collab.prenom
            user.last_name = collab.nom
            if password:
                user.set_password(password)
            user.save()
        else:
            # Création : on crée un User non-admin lié au collaborateur
            user = User(
                username=email, email=email,
                first_name=collab.prenom, last_name=collab.nom,
                is_staff=False, is_active=True,
            )
            user.set_password(password)
            user.save()
            collab.user = user

        if commit:
            collab.save()
            self.save_m2m()
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
    """Formulaire restreint réservé à l'évalué.

    L'évalué renseigne son responsable hiérarchique, ses faits marquants,
    ses initiatives personnelles. L'évaluateur (préchargé) est en lecture
    seule pour information.
    """

    class Meta:
        model = Evaluation
        fields = ["responsable_hierarchique", "initiatives_personnelles"]
        widgets = {
            "responsable_hierarchique": forms.TextInput(attrs={"class": INPUT}),
            "initiatives_personnelles": forms.Textarea(attrs={"class": TEXTAREA, "rows": 4}),
        }
        labels = {
            "responsable_hierarchique": "Responsable hiérarchique / point focal",
        }


class ObjectifEvalueForm(forms.ModelForm):
    """Formulaire d'un objectif vu par l'évalué : il se note (taux d'atteinte)
    et écrit son commentaire. Le titre/description/livrables/coefficient
    restent en lecture seule (viennent du catalogue de son unité).
    """

    class Meta:
        model = Objectif
        fields = ["taux_atteinte", "commentaire_evalue"]
        widgets = {
            "taux_atteinte": forms.NumberInput(
                attrs={"class": INPUT + " taux-input", "step": "1", "min": 0, "max": 100}
            ),
            "commentaire_evalue": forms.Textarea(attrs={"class": TEXTAREA, "rows": 2}),
        }


ObjectifEvalueFormSet = inlineformset_factory(
    Evaluation,
    Objectif,
    form=ObjectifEvalueForm,
    extra=0,
    can_delete=False,
)


class FaitMarquantForm(forms.ModelForm):
    class Meta:
        model = FaitMarquant
        fields = ["ordre", "fait", "observation"]
        widgets = {
            "ordre": forms.NumberInput(attrs={
                "class": LOCKED_INPUT + " w-16 text-center",
                "readonly": "readonly", "tabindex": "-1",
            }),
            "fait": forms.Textarea(attrs={"class": TEXTAREA, "rows": 2, "placeholder": "Décrivez un fait marquant…"}),
            "observation": forms.Textarea(attrs={"class": TEXTAREA, "rows": 2, "placeholder": "Vos observations sur ce fait (optionnel)"}),
        }


FaitMarquantFormSet = inlineformset_factory(
    Evaluation,
    FaitMarquant,
    form=FaitMarquantForm,
    extra=3,  # 3 lignes vides par défaut pour rappeler le format du formulaire papier
    can_delete=True,
    min_num=0,
)


class ObjectifForm(forms.ModelForm):
    """Formulaire d'objectif côté évaluateur.

    L'évaluateur peut modifier le taux d'atteinte (que l'évalué s'est attribué)
    et son propre commentaire. Tout le reste — titre/description/livrables/
    coefficient (catalogue) et commentaire de l'évalué — est en lecture seule.
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
        fields = ["unite", "titre", "description", "livrables", "coefficient", "ordre", "actif"]
        widgets = {
            "unite": forms.Select(attrs={"class": SELECT}),
            "titre": forms.TextInput(attrs={"class": INPUT}),
            "description": forms.Textarea(attrs={"class": TEXTAREA, "rows": 3}),
            "livrables": forms.Textarea(attrs={"class": TEXTAREA, "rows": 2}),
            "coefficient": forms.NumberInput(attrs={"class": INPUT, "step": "0.5", "min": 0}),
            "ordre": forms.NumberInput(attrs={"class": INPUT, "min": 0}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["unite"].required = True
        self.fields["unite"].queryset = Unite.objects.filter(actif=True).order_by("ordre", "libelle")


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


class MonCompteForm(forms.ModelForm):
    """Édition de son propre compte.

    - first_name et last_name sont toujours éditables
    - email est éditable uniquement par les admins (pour les non-admins, c'est
      leur identifiant de connexion donc immuable)
    """

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]
        labels = {
            "first_name": "Prénom",
            "last_name": "Nom",
            "email": "Adresse email",
        }
        widgets = {
            "first_name": forms.TextInput(attrs={"class": INPUT}),
            "last_name": forms.TextInput(attrs={"class": INPUT}),
            "email": forms.EmailInput(attrs={"class": INPUT}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._editing_user = user
        # Si l'utilisateur n'est pas admin, on verrouille son email
        if user is not None and not user.is_staff:
            self.fields["email"].disabled = True
            self.fields["email"].help_text = "Votre email est votre identifiant de connexion ; seul un administrateur peut le modifier."

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if not email:
            raise ValidationError("L'adresse email est obligatoire.")
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise ValidationError("Cette adresse email est déjà utilisée par un autre compte.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        # Si admin a modifié l'email, on resync le username (le username est l'email pour nos comptes)
        if self.cleaned_data.get("email") and user.is_staff:
            user.username = self.cleaned_data["email"]
        if commit:
            user.save()
            # Synchroniser le profil collaborateur lié si présent
            from .models import Collaborateur
            collab = Collaborateur.objects.filter(user=user).first()
            if collab:
                collab.prenom = user.first_name
                collab.nom = user.last_name
                collab.save(update_fields=["prenom", "nom"])
        return user

