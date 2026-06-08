import json
from decimal import Decimal
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count
from django.forms import inlineformset_factory
from django.shortcuts import get_object_or_404, redirect, render

from django.contrib.auth import get_user_model

from .forms import (
    CollaborateurForm,
    EvaluationEvalueForm,
    EvaluationForm,
    FaitMarquantFormSet,
    MonCompteForm,
    NiveauAppreciationForm,
    ObjectifCatalogueForm,
    ObjectifEvalueFormSet,
    ObjectifForm,
    ObjectifFormSet,
    UtilisateurCreationForm,
    UtilisateurEditForm,
    UtilisateurResetPasswordForm,
)
from .models import (
    AuditLog,
    Collaborateur,
    Evaluation,
    NiveauAppreciation,
    Objectif,
    ObjectifCatalogue,
    Unite,
    UserPreference,
)

User = get_user_model()


admin_required = user_passes_test(lambda u: u.is_authenticated and u.is_staff)


def _dec(value):
    return float(value) if isinstance(value, Decimal) else value


@login_required
def dashboard(request):
    profil_collab = getattr(request.user, "profil_collaborateur", None)

    # Évalué non admin : tableau de bord dédié, sans les fonctions évaluateur.
    if profil_collab and not request.user.is_staff:
        mes_evaluations = list(
            profil_collab.evaluations.prefetch_related("objectifs").order_by("-date_evaluation")
        )
        eval_en_cours = next(
            (e for e in mes_evaluations
             if e.statut in [Evaluation.Statut.BROUILLON, Evaluation.Statut.SOUMISE]),
            None,
        )
        # L'unité du collaborateur a-t-elle des objectifs ? (pour message dashboard)
        objectifs_unite = []
        if profil_collab.unite:
            objectifs_unite = list(
                ObjectifCatalogue.objects.filter(unite=profil_collab.unite, actif=True)
                .order_by("ordre", "id")
            )
        unite_sans_objectifs = profil_collab.unite is not None and not objectifs_unite

        # Évaluations finalisées (Validée ou Visée RH) pour la courbe d'évolution
        evals_finalisees = [
            e for e in mes_evaluations
            if e.statut in [Evaluation.Statut.VALIDEE, Evaluation.Statut.VISEE_RH]
            and e.note_globale is not None
        ]
        # Tri chronologique ascendant pour la courbe
        evals_finalisees_chrono = sorted(evals_finalisees, key=lambda e: e.date_evaluation)
        evolution = {
            "labels": [e.date_evaluation.strftime("%d/%m/%Y") for e in evals_finalisees_chrono],
            "notes": [_dec(e.note_globale) for e in evals_finalisees_chrono],
        }
        # Dernière évaluation finalisée (pour montrer la dernière note/appréciation)
        derniere_finalisee = evals_finalisees_chrono[-1] if evals_finalisees_chrono else None

        return render(request, "evaluations/dashboard_evalue.html", {
            "profil_collab": profil_collab,
            "evaluations": mes_evaluations,
            "eval_en_cours": eval_en_cours,
            "unite_sans_objectifs": unite_sans_objectifs,
            "objectifs_unite": objectifs_unite,
            "nb_evals_finalisees": len(evals_finalisees),
            "derniere_finalisee": derniere_finalisee,
            "evolution_json": json.dumps(evolution),
            "Statut": Evaluation.Statut,
        })

    # Sinon : tableau de bord évaluateur / admin
    # - Admin voit toutes les évaluations
    # - Évaluateur ne voit que les évaluations des collaborateurs qu'il évalue
    evaluations_qs = Evaluation.objects.select_related("collaborateur").prefetch_related("objectifs")
    collaborateurs_qs = Collaborateur.objects.filter(actif=True)
    if not request.user.is_staff:
        evaluations_qs = evaluations_qs.filter(collaborateur__evaluateur=request.user)
        collaborateurs_qs = collaborateurs_qs.filter(evaluateur=request.user)
    evaluations = list(evaluations_qs)

    # Évaluations qui attendent l'action de l'évaluateur connecté :
    # SOUMISE = l'évalué a transmis, l'évaluateur doit revoir et valider.
    evals_a_valider = [e for e in evaluations if e.statut == Evaluation.Statut.SOUMISE]
    lignes = []
    for ev in evaluations[:15]:
        lignes.append({"ev": ev, "note": ev.note_globale, "appreciation": ev.appreciation})

    notes_dispo = [e.note_globale for e in evaluations if e.note_globale is not None]
    note_moyenne = (
        (sum(notes_dispo) / len(notes_dispo)).quantize(Decimal("0.01"))
        if notes_dispo else None
    )

    context = {
        "lignes": lignes,
        "nb_collaborateurs": collaborateurs_qs.count(),
        "nb_evaluations": len(evaluations),
        "evals_a_valider": evals_a_valider,
        "Statut": Evaluation.Statut,
        "nb_objectifs_catalogue": ObjectifCatalogue.objects.filter(actif=True).count(),
        "note_moyenne": note_moyenne,
        "bareme": NiveauAppreciation.objects.all(),
        # Bandeau "Vous êtes aussi évalué" pour les admins/évaluateurs qui ont
        # eux-mêmes un profil collaborateur (cas double rôle).
        "profil_collab": profil_collab,
        "mes_evaluations": (
            list(profil_collab.evaluations.prefetch_related("objectifs").order_by("-date_evaluation"))
            if profil_collab else []
        ),
    }
    return render(request, "evaluations/dashboard.html", context)


@login_required
def collaborateur_list(request):
    from django.db.models import Q
    # Admin voit tous les collaborateurs ; évaluateur ne voit que les siens.
    qs = Collaborateur.objects.select_related("unite", "evaluateur").annotate(nb_eval=Count("evaluations"))
    if not request.user.is_staff:
        qs = qs.filter(evaluateur=request.user)

    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(nom__icontains=q)
            | Q(prenom__icontains=q)
            | Q(poste__icontains=q)
            | Q(direction__icontains=q)
            | Q(projets__icontains=q)
            | Q(unite__libelle__icontains=q)
        )

    context = {"collaborateurs": list(qs), "q": q}
    # Si la requête vient de HTMX, on renvoie uniquement la grille (recherche live)
    if getattr(request, "htmx", False):
        return render(request, "evaluations/_collaborateur_grid.html", context)
    return render(request, "evaluations/collaborateur_list.html", context)


@login_required
@admin_required
def collaborateur_create(request):
    form = CollaborateurForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        collab = form.save()
        messages.success(request, "Collaborateur enregistré.")
        return redirect(collab.get_absolute_url())
    return render(
        request,
        "evaluations/collaborateur_form.html",
        {"form": form, "titre": "Nouveau collaborateur"},
    )


@login_required
@admin_required
def collaborateur_edit(request, collab_uuid):
    """Édition d'un collaborateur existant : surtout pour affecter
    son unité et son évaluateur quand ce n'était pas le cas à la création."""
    collab = get_object_or_404(Collaborateur, uuid=collab_uuid)
    form = CollaborateurForm(request.POST or None, instance=collab)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Modifications enregistrées.")
        return redirect(collab.get_absolute_url())
    return render(
        request,
        "evaluations/collaborateur_form.html",
        {"form": form, "titre": f"Modifier · {collab.nom_complet}", "collab": collab},
    )


@login_required
def collaborateur_detail(request, collab_uuid):
    collab = get_object_or_404(Collaborateur, uuid=collab_uuid)
    evaluations = list(collab.evaluations.prefetch_related("objectifs").all())
    historique = sorted(evaluations, key=lambda e: e.date_evaluation)
    evolution = {
        "labels": [e.date_evaluation.strftime("%d/%m/%Y") for e in historique],
        "notes": [_dec(e.note_globale) for e in historique],
    }

    # Sélection de l'évaluation à afficher dans le radar / les scores
    # On filtre par UUID (et non plus par pk) pour ne pas exposer le compteur séquentiel.
    selected_id = request.GET.get("eval")
    selected = None
    if selected_id:
        for e in evaluations:
            if str(e.uuid) == str(selected_id):
                selected = e
                break
    if selected is None:
        selected = historique[-1] if historique else None

    radar = {"labels": [], "titres": [], "taux": []}
    objectifs_focus = []
    if selected:
        objectifs_focus = list(selected.objectifs.all())
        for obj in objectifs_focus:
            radar["labels"].append(f"Obj {obj.numero}")
            radar["titres"].append(obj.titre or obj.description or f"Objectif {obj.numero}")
            radar["taux"].append(_dec(obj.taux_atteinte))

    context = {
        "collab": collab,
        "evaluations": sorted(evaluations, key=lambda e: e.date_evaluation, reverse=True),
        "evolution_json": json.dumps(evolution),
        "radar_json": json.dumps(radar),
        "selected": selected,
        "objectifs_focus": objectifs_focus,
        "selected_note": selected.note_globale if selected else None,
        "selected_appreciation": selected.appreciation if selected else None,
    }
    return render(request, "evaluations/collaborateur_detail.html", context)


@login_required
def evaluation_create(request):
    return _evaluation_form(request, evaluation=None)


@login_required
def evaluation_edit(request, eval_uuid):
    evaluation = get_object_or_404(Evaluation, uuid=eval_uuid)
    # Si l'utilisateur est l'évalué (non admin), il a une vue restreinte.
    if evaluation.est_evalue(request.user) and not request.user.is_staff:
        return redirect("evaluations:evaluation_evalue_edit", eval_uuid=evaluation.uuid)
    return _evaluation_form(request, evaluation=evaluation)


@login_required
def evaluation_start(request):
    """Permet à un évalué de démarrer sa propre évaluation.

    Conditions :
    - L'utilisateur doit avoir un profil collaborateur (être un évalué)
    - Son profil doit être rattaché à une unité (sinon pas d'objectifs à proposer)
    - Il ne doit pas avoir d'évaluation déjà en cours (Brouillon ou Soumise)
    """
    profil = getattr(request.user, "profil_collaborateur", None)
    if not profil:
        messages.error(request, "Votre compte ne permet pas de démarrer une évaluation.")
        return redirect("evaluations:dashboard")
    if not profil.unite:
        messages.error(
            request,
            "Aucune unité n'est associée à votre profil. Contactez l'administrateur."
        )
        return redirect("evaluations:dashboard")

    # Vérifier que l'unité a des objectifs configurés
    nb_objectifs = ObjectifCatalogue.objects.filter(unite=profil.unite, actif=True).count()
    if nb_objectifs == 0:
        messages.error(
            request,
            f"Les objectifs n'ont pas encore été configurés pour l'unité « {profil.unite.libelle} ». "
            "Veuillez vous rapprocher de votre évaluateur ou d'un administrateur de la plateforme."
        )
        return redirect("evaluations:dashboard")

    # Une seule évaluation ouverte à la fois
    existante = profil.evaluations.filter(
        statut__in=[Evaluation.Statut.BROUILLON, Evaluation.Statut.SOUMISE]
    ).first()
    if existante:
        messages.warning(
            request,
            "Vous avez déjà une évaluation en cours. Terminez-la avant d'en démarrer une nouvelle."
        )
        return redirect("evaluations:evaluation_evalue_edit", eval_uuid=existante.uuid)

    # Création de l'évaluation
    evaluation = Evaluation.objects.create(
        collaborateur=profil,
        evaluateur=(profil.evaluateur.get_full_name() or profil.evaluateur.email) if profil.evaluateur else "",
        statut=Evaluation.Statut.BROUILLON,
    )
    # Pré-remplir les objectifs depuis le catalogue de l'unité
    evaluation.remplir_objectifs_depuis_catalogue()

    messages.success(
        request,
        "Évaluation démarrée. Renseignez vos faits marquants, initiatives et notez vos objectifs."
    )
    return redirect("evaluations:evaluation_evalue_edit", eval_uuid=evaluation.uuid)


@login_required
def evaluation_evalue_edit(request, eval_uuid):
    """Vue de saisie de l'évalué : faits marquants, initiatives, taux d'atteinte
    par objectif, commentaire par objectif. L'évalué peut soumettre à son
    évaluateur depuis cette page.
    """
    evaluation = get_object_or_404(
        Evaluation.objects.select_related("collaborateur"), uuid=eval_uuid
    )
    # Sécurité : seul l'évalué de cette évaluation (ou un admin) peut y accéder
    if not evaluation.est_evalue(request.user) and not request.user.is_staff:
        messages.error(request, "Vous n'êtes pas autorisé à modifier cette évaluation.")
        return redirect(evaluation.get_absolute_url())

    locked = not evaluation.peut_etre_modifie_par_evalue()

    if request.method == "POST" and locked:
        messages.warning(
            request,
            "Cette évaluation est déjà entre les mains de votre évaluateur ; vous ne pouvez plus la modifier."
        )
        return redirect(evaluation.get_absolute_url())

    if request.method == "POST":
        form = EvaluationEvalueForm(request.POST, instance=evaluation)
        formset = ObjectifEvalueFormSet(request.POST, instance=evaluation)
        faits_formset = FaitMarquantFormSet(request.POST, instance=evaluation)
        if form.is_valid() and formset.is_valid() and faits_formset.is_valid():
            form.save()
            formset.save()
            faits_formset.save()
            # Action "Soumettre à l'évaluateur" ?
            if request.POST.get("action") == "submit":
                evaluation.statut = Evaluation.Statut.SOUMISE
                evaluation.save(update_fields=["statut"])
                messages.success(
                    request,
                    "Évaluation envoyée à votre évaluateur. Vous ne pourrez plus la modifier."
                )
            else:
                messages.success(request, "Vos informations ont été enregistrées.")
            return redirect(evaluation.get_absolute_url())
    else:
        form = EvaluationEvalueForm(instance=evaluation)
        formset = ObjectifEvalueFormSet(instance=evaluation)
        faits_formset = FaitMarquantFormSet(instance=evaluation)

    # Évaluateur affiché en lecture seule
    nom_evaluateur = evaluation.evaluateur or (
        evaluation.collaborateur.evaluateur.get_full_name() or evaluation.collaborateur.evaluateur.email
        if evaluation.collaborateur.evaluateur_id else "Non assigné"
    )

    return render(request, "evaluations/evaluation_evalue_form.html", {
        "evaluation": evaluation,
        "form": form,
        "formset": formset,
        "faits_formset": faits_formset,
        "objectifs": list(evaluation.objectifs.all()),
        "nom_evaluateur": nom_evaluateur,
        "locked": locked,
    })


@login_required
def evaluation_change_statut(request, eval_uuid):
    """Transition de statut côté évaluateur : Brouillon -> Soumise -> Validée -> Visée RH."""
    if request.method != "POST":
        return redirect("evaluations:dashboard")
    evaluation = get_object_or_404(Evaluation, uuid=eval_uuid)
    # L'évalué ne peut pas changer le statut.
    if evaluation.est_evalue(request.user) and not request.user.is_staff:
        messages.error(request, "Vous n'êtes pas autorisé à changer le statut de cette évaluation.")
        return redirect(evaluation.get_absolute_url())

    target = request.POST.get("statut")
    valid_transitions = {
        Evaluation.Statut.BROUILLON: [Evaluation.Statut.SOUMISE],
        Evaluation.Statut.SOUMISE: [Evaluation.Statut.BROUILLON, Evaluation.Statut.VALIDEE],
        Evaluation.Statut.VALIDEE: [Evaluation.Statut.SOUMISE, Evaluation.Statut.VISEE_RH],
        Evaluation.Statut.VISEE_RH: [],
    }
    allowed = valid_transitions.get(evaluation.statut, [])
    # Visa RH réservé aux admins
    if target == Evaluation.Statut.VISEE_RH and not request.user.is_staff:
        messages.error(request, "Seul un administrateur peut apposer le visa RH.")
        return redirect(evaluation.get_absolute_url())

    if target in allowed:
        ancien = evaluation.statut
        evaluation.statut = target
        evaluation.save(update_fields=["statut"])
        labels = dict(Evaluation.Statut.choices)
        AuditLog.log(
            acteur=request.user,
            action=AuditLog.Action.STATUT,
            description=f"Évaluation {evaluation} : statut {labels.get(ancien, ancien)} → {labels.get(target, target)}",
            modele="Evaluation",
            objet_id=evaluation.pk,
            cible_user=evaluation.collaborateur.user,
        )
        messages.success(request, f"Statut mis à jour : {labels.get(target, target)}.")
    else:
        messages.warning(request, "Transition de statut invalide.")
    return redirect(evaluation.get_absolute_url())


def _evaluation_form(request, evaluation):
    is_create = evaluation is None

    if request.method == "POST":
        form = EvaluationForm(request.POST, instance=evaluation)
        formset = ObjectifFormSet(
            request.POST, instance=evaluation or Evaluation()
        )
        if form.is_valid() and formset.is_valid():
            was_create = evaluation is None
            evaluation = form.save()
            formset.instance = evaluation
            formset.save()
            if was_create and evaluation.collaborateur.user_id:
                messages.success(
                    request,
                    f"Évaluation créée. {evaluation.collaborateur.nom_complet} "
                    f"peut maintenant compléter ses parties depuis son espace.",
                )
            elif was_create:
                messages.success(
                    request,
                    f"Évaluation créée. Le collaborateur n'a pas de compte d'accès : "
                    f"il ne pourra pas remplir ses propres parties en ligne tant qu'un "
                    f"compte ne lui aura pas été créé.",
                )
            else:
                messages.success(request, "Évaluation enregistrée.")
            return redirect(evaluation.get_absolute_url())
    else:
        initial_data = {}
        if is_create:
            # Pré-remplir l'évaluateur avec l'utilisateur connecté
            nom_evaluateur = request.user.get_full_name() or request.user.email
            initial_data["evaluateur"] = nom_evaluateur
        form = EvaluationForm(instance=evaluation, initial=initial_data)
        if is_create:
            catalog_items = list(
                ObjectifCatalogue.objects.filter(actif=True).order_by("ordre", "id")
            )
            initial = [
                {
                    "numero": idx,
                    "titre": cat.titre,
                    "description": cat.description,
                    "livrables": cat.livrables,
                    "coefficient": cat.coefficient,
                    "taux_atteinte": 0,
                }
                for idx, cat in enumerate(catalog_items, start=1)
            ]
            DynFormSet = inlineformset_factory(
                Evaluation,
                Objectif,
                form=ObjectifForm,
                extra=max(len(initial), 1),
                can_delete=True,
            )
            formset = DynFormSet(initial=initial, instance=Evaluation())
        else:
            formset = ObjectifFormSet(instance=evaluation)

    titre = "Modifier l'évaluation" if evaluation else "Nouvelle évaluation"
    return render(
        request,
        "evaluations/evaluation_form.html",
        {"form": form, "formset": formset, "titre": titre, "evaluation": evaluation},
    )


@login_required
def evaluation_detail(request, eval_uuid):
    evaluation = get_object_or_404(
        Evaluation.objects.select_related("collaborateur"), uuid=eval_uuid
    )
    objectifs = list(evaluation.objectifs.all())
    radar = {
        "labels": [f"Obj {o.numero}" for o in objectifs],
        "titres": [o.titre or o.description or f"Objectif {o.numero}" for o in objectifs],
        "taux": [_dec(o.taux_atteinte) for o in objectifs],
    }
    is_evalue = evaluation.est_evalue(request.user)
    is_admin = request.user.is_staff
    # Évalué simple (non admin) : interface restreinte
    role_evalue_seul = is_evalue and not is_admin

    # État du partage avec l'évalué (pour la vue évaluateur)
    collab = evaluation.collaborateur
    evalue_a_un_compte = collab.user_id is not None
    evalue_a_commence = bool(
        evaluation.faits_marquants
        or evaluation.initiatives_personnelles
        or any(o.commentaire_evalue for o in objectifs)
    )

    context = {
        "evaluation": evaluation,
        "objectifs": objectifs,
        "note": evaluation.note_globale,
        "appreciation": evaluation.appreciation,
        "radar_json": json.dumps(radar),
        "is_evalue": is_evalue,
        "is_admin": is_admin,
        "role_evalue_seul": role_evalue_seul,
        "peut_modifier_evalue": evaluation.peut_etre_modifie_par_evalue(),
        "peut_modifier_evaluateur": evaluation.peut_etre_modifie_par_evaluateur(),
        "Statut": Evaluation.Statut,
        "evalue_a_un_compte": evalue_a_un_compte,
        "evalue_a_commence": evalue_a_commence,
    }
    return render(request, "evaluations/evaluation_detail.html", context)


@login_required
@admin_required
def evaluation_delete(request, eval_uuid):
    """Suppression définitive d'une évaluation par un admin."""
    evaluation = get_object_or_404(Evaluation, uuid=eval_uuid)
    if request.method == "POST":
        collab = evaluation.collaborateur
        label = f"{collab.nom_complet} - {evaluation.date_evaluation:%d/%m/%Y}"
        evaluation.delete()
        messages.success(request, f"Évaluation supprimée : {label}.")
        return redirect(collab.get_absolute_url())
    # Sinon (GET) : on redirige vers la fiche (le bouton de suppression est sur la fiche détail)
    return redirect(evaluation.get_absolute_url())


@login_required
def evaluation_print(request, eval_uuid):
    evaluation = get_object_or_404(
        Evaluation.objects.select_related("collaborateur"), uuid=eval_uuid
    )
    context = {
        "evaluation": evaluation,
        "objectifs": list(evaluation.objectifs.all()),
        "note": evaluation.note_globale,
        "appreciation": evaluation.appreciation,
    }
    return render(request, "evaluations/evaluation_print.html", context)


# ============================================================================
# Espace administration in-app (accessible uniquement aux utilisateurs is_staff)
# ============================================================================

@login_required
@admin_required
def admin_home(request):
    return redirect("evaluations:admin_utilisateurs")


# --- Utilisateurs ----------------------------------------------------------

@login_required
@admin_required
def admin_utilisateurs(request):
    utilisateurs = User.objects.all().order_by("-is_staff", "username")
    # Mappe user_id -> Collaborateur pour distinguer évalués et évaluateurs
    collab_par_user = {
        c.user_id: c
        for c in Collaborateur.objects.filter(user__isnull=False).only("id", "uuid", "nom", "prenom", "type", "user_id")
    }
    rows = []
    for u in utilisateurs:
        collab = collab_par_user.get(u.id)
        if collab:
            role = "evalue"
        elif u.is_staff:
            role = "admin"
        else:
            role = "evaluateur"
        rows.append({"u": u, "collab": collab, "role": role})
    return render(request, "evaluations/admin/utilisateurs_list.html", {
        "rows": rows,
        "nb_evalues": sum(1 for r in rows if r["role"] == "evalue"),
        "nb_evaluateurs": sum(1 for r in rows if r["role"] == "evaluateur"),
        "nb_admins": sum(1 for r in rows if r["role"] == "admin"),
    })


@login_required
@admin_required
def admin_utilisateur_create(request):
    form = UtilisateurCreationForm(request.POST or None)
    created_user = None
    if request.method == "POST" and form.is_valid():
        created_user = form.save()
        messages.success(
            request,
            f"Compte créé pour {created_user.email}. "
            f"Mot de passe provisoire : {form.cleaned_data['password1']} (à transmettre à la personne)."
        )
        return redirect("evaluations:admin_utilisateur_edit", pk=created_user.pk)
    return render(request, "evaluations/admin/utilisateur_form.html", {
        "form": form, "titre": "Nouveau compte", "is_create": True,
    })


@login_required
@admin_required
def admin_utilisateur_edit(request, pk):
    utilisateur = get_object_or_404(User, pk=pk)
    form = UtilisateurEditForm(request.POST or None, instance=utilisateur)
    reset_form = UtilisateurResetPasswordForm()
    if request.method == "POST" and "save_info" in request.POST and form.is_valid():
        # Empêcher de se retirer ses propres droits admin par mégarde
        if utilisateur == request.user and not form.cleaned_data.get("is_staff"):
            messages.warning(request, "Vous ne pouvez pas retirer vos propres privilèges admin.")
            form.cleaned_data["is_staff"] = True
            utilisateur.is_staff = True
            utilisateur.first_name = form.cleaned_data["first_name"]
            utilisateur.last_name = form.cleaned_data["last_name"]
            utilisateur.email = form.cleaned_data["email"]
            utilisateur.is_active = True
            utilisateur.save()
        else:
            form.save()
            messages.success(request, "Informations enregistrées.")
        return redirect("evaluations:admin_utilisateur_edit", pk=utilisateur.pk)
    return render(request, "evaluations/admin/utilisateur_form.html", {
        "form": form, "reset_form": reset_form,
        "titre": f"Compte de {utilisateur.email or utilisateur.username}",
        "utilisateur": utilisateur, "is_create": False,
    })


@login_required
@admin_required
def admin_utilisateur_reset_password(request, pk):
    utilisateur = get_object_or_404(User, pk=pk)
    if request.method == "POST":
        form = UtilisateurResetPasswordForm(request.POST)
        if form.is_valid():
            utilisateur.set_password(form.cleaned_data["password"])
            utilisateur.save(update_fields=["password"])
            AuditLog.log(
                acteur=request.user,
                action=AuditLog.Action.PASSWORD,
                description=f"Mot de passe réinitialisé par un administrateur pour {utilisateur.email or utilisateur.username}",
                modele="User",
                objet_id=utilisateur.pk,
                cible_user=utilisateur,
            )
            messages.success(
                request,
                f"Mot de passe réinitialisé. Nouveau mot de passe : {form.cleaned_data['password']} (à transmettre)."
            )
    return redirect("evaluations:admin_utilisateur_edit", pk=utilisateur.pk)


# --- Catalogue d'objectifs -------------------------------------------------

@login_required
@admin_required
def admin_catalogue(request):
    # Filtre par unité via ?unite=<code>
    unite_code = request.GET.get("unite")
    unites = list(Unite.objects.filter(actif=True))
    objectifs_qs = (
        ObjectifCatalogue.objects.select_related("unite")
        .order_by("unite__ordre", "ordre", "id")
    )
    unite_active = None
    if unite_code:
        unite_active = next((u for u in unites if u.code == unite_code), None)
        if unite_active:
            objectifs_qs = objectifs_qs.filter(unite=unite_active)

    # Regrouper par unité pour l'affichage
    groupes = []
    for unite in unites:
        objs = [o for o in objectifs_qs if o.unite_id == unite.id]
        if unite_active and unite_active != unite:
            continue
        groupes.append({
            "unite": unite,
            "objectifs": objs,
        })
    # Objectifs sans unité (legacy)
    orphans = [o for o in objectifs_qs if o.unite_id is None]
    if orphans and not unite_active:
        groupes.append({"unite": None, "objectifs": orphans})

    return render(request, "evaluations/admin/catalogue_list.html", {
        "groupes": groupes,
        "unites": unites,
        "unite_active": unite_active,
    })


@login_required
@admin_required
def admin_objectif_create(request):
    # Pré-sélection de l'unité via ?unite=<code>
    initial = {}
    unite_code = request.GET.get("unite")
    if unite_code:
        unite = Unite.objects.filter(code=unite_code).first()
        if unite:
            initial["unite"] = unite
    form = ObjectifCatalogueForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        messages.success(request, "Objectif ajouté au catalogue.")
        if obj.unite:
            from django.urls import reverse as _r
            return redirect(f"{_r('evaluations:admin_catalogue')}?unite={obj.unite.code}")
        return redirect("evaluations:admin_catalogue")
    return render(request, "evaluations/admin/objectif_form.html", {
        "form": form, "titre": "Nouvel objectif",
    })


@login_required
@admin_required
def admin_objectif_edit(request, pk):
    obj = get_object_or_404(ObjectifCatalogue, pk=pk)
    form = ObjectifCatalogueForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Objectif mis à jour.")
        return redirect("evaluations:admin_catalogue")
    return render(request, "evaluations/admin/objectif_form.html", {
        "form": form, "titre": f"Modifier · {obj.titre}", "objet": obj,
    })


@login_required
@admin_required
def admin_objectif_delete(request, pk):
    obj = get_object_or_404(ObjectifCatalogue, pk=pk)
    if request.method == "POST":
        titre = obj.titre
        obj.delete()
        messages.success(request, f"Objectif supprimé : {titre}.")
    return redirect("evaluations:admin_catalogue")


# --- Journal d'audit -------------------------------------------------------

@login_required
def audit_log(request):
    """Page de consultation du journal d'audit.

    - Admin : voit tous les logs
    - Non-admin : voit uniquement les logs où il est acteur OU cible
    Chaque utilisateur peut "vider" sa vue personnelle (les logs restent en base).
    """
    from django.db.models import Q
    qs = AuditLog.objects.select_related("acteur", "cible_user").all()
    if not request.user.is_staff:
        qs = qs.filter(Q(acteur=request.user) | Q(cible_user=request.user))

    # Filtrage personnel : si l'utilisateur a vidé ses logs récemment, on ne
    # lui montre que ceux postérieurs au timestamp.
    pref = UserPreference.objects.filter(user=request.user).first()
    if pref and pref.audit_cleared_at:
        qs = qs.filter(date__gt=pref.audit_cleared_at)

    # Filtre par recherche textuelle simple
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(description__icontains=q)
            | Q(acteur__email__icontains=q)
            | Q(acteur__first_name__icontains=q)
            | Q(acteur__last_name__icontains=q)
            | Q(cible_user__email__icontains=q)
        )
    # Filtre par type d'action
    action_filter = request.GET.get("action")
    if action_filter:
        qs = qs.filter(action=action_filter)

    # Pagination simple : 50 entrées par page
    from django.core.paginator import Paginator
    paginator = Paginator(qs, 50)
    page_num = request.GET.get("page") or 1
    page = paginator.get_page(page_num)

    return render(request, "evaluations/audit_log.html", {
        "page": page,
        "q": q,
        "action_filter": action_filter,
        "actions_disponibles": AuditLog.Action.choices,
        "has_cleared": bool(pref and pref.audit_cleared_at),
    })


@login_required
def mon_compte(request):
    """Page où chacun édite ses propres infos (nom, prénom, email pour les admins)."""
    form = MonCompteForm(request.POST or None, instance=request.user, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Vos informations ont été mises à jour.")
        return redirect("evaluations:mon_compte")
    return render(request, "evaluations/mon_compte.html", {
        "form": form,
        "profil_collab": getattr(request.user, "profil_collaborateur", None),
    })


@login_required
def audit_log_clear(request):
    """Vide la vue personnelle du journal pour l'utilisateur courant.

    Les entrées restent en base de données (pour l'audit administrateur).
    Seule la vue de cet utilisateur les masque désormais.
    """
    if request.method == "POST":
        from django.utils import timezone as _tz
        pref, _ = UserPreference.objects.get_or_create(user=request.user)
        pref.audit_cleared_at = _tz.now()
        pref.save()
        messages.success(
            request,
            "Votre journal personnel a été vidé. Les entrées restent disponibles "
            "pour les administrateurs."
        )
    return redirect("evaluations:audit_log")


# --- Statistiques par unité (admin) ----------------------------------------

@login_required
@admin_required
def admin_statistiques(request):
    """Tableau de bord statistique : note moyenne par unité, distribution
    d'appréciations, comptes par statut."""
    import json as _json
    unites = list(Unite.objects.filter(actif=True).order_by("ordre", "libelle"))

    # Évaluations validées ou visées RH = finalisées, comparables.
    evals_finalisees = list(
        Evaluation.objects.filter(
            statut__in=[Evaluation.Statut.VALIDEE, Evaluation.Statut.VISEE_RH]
        ).select_related("collaborateur__unite").prefetch_related("objectifs")
    )

    # Note moyenne par unité (sur les évals finalisées)
    moyennes = []
    for u in unites:
        notes = [
            e.note_globale for e in evals_finalisees
            if e.collaborateur.unite_id == u.id and e.note_globale is not None
        ]
        if notes:
            moy = (sum(notes) / len(notes)).quantize(Decimal("0.01"))
        else:
            moy = None
        moyennes.append({
            "unite": u, "moyenne": moy, "nb": len(notes),
        })

    # Distribution des appréciations (toutes unités confondues)
    distribution = {}
    for e in evals_finalisees:
        appr = e.appreciation
        key = appr.libelle if appr else "Sans appréciation"
        if key not in distribution:
            distribution[key] = {"count": 0, "couleur": appr.couleur if appr else "#94a3b8"}
        distribution[key]["count"] += 1

    # Évaluations par statut (toutes)
    statuts_count = {label: 0 for code, label in Evaluation.Statut.choices}
    for e in Evaluation.objects.all().only("statut"):
        label = dict(Evaluation.Statut.choices).get(e.statut, e.statut)
        statuts_count[label] = statuts_count.get(label, 0) + 1

    # Évaluations par unité (toutes statuts confondus)
    nb_par_unite = []
    for u in unites:
        count = Evaluation.objects.filter(collaborateur__unite=u).count()
        nb_par_unite.append({"unite": u, "count": count})

    # JSON pour Chart.js
    moyennes_chart = {
        "labels": [m["unite"].libelle for m in moyennes],
        "values": [float(m["moyenne"]) if m["moyenne"] is not None else 0 for m in moyennes],
        "counts": [m["nb"] for m in moyennes],
    }
    distribution_chart = {
        "labels": list(distribution.keys()),
        "values": [d["count"] for d in distribution.values()],
        "colors": [d["couleur"] for d in distribution.values()],
    }
    statuts_chart = {
        "labels": list(statuts_count.keys()),
        "values": list(statuts_count.values()),
    }

    return render(request, "evaluations/admin/statistiques.html", {
        "moyennes": moyennes,
        "nb_par_unite": nb_par_unite,
        "moyennes_json": _json.dumps(moyennes_chart),
        "distribution_json": _json.dumps(distribution_chart),
        "statuts_json": _json.dumps(statuts_chart),
        "nb_evals_finalisees": len(evals_finalisees),
        "nb_evals_total": sum(statuts_count.values()),
    })


# --- Barème d'appréciation -------------------------------------------------

@login_required
@admin_required
def admin_bareme(request):
    niveaux = NiveauAppreciation.objects.all().order_by("-seuil_min")
    return render(request, "evaluations/admin/bareme_list.html", {"niveaux": niveaux})


@login_required
@admin_required
def admin_niveau_create(request):
    form = NiveauAppreciationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Niveau ajouté au barème.")
        return redirect("evaluations:admin_bareme")
    return render(request, "evaluations/admin/niveau_form.html", {
        "form": form, "titre": "Nouveau niveau d'appréciation",
    })


@login_required
@admin_required
def admin_niveau_edit(request, pk):
    niv = get_object_or_404(NiveauAppreciation, pk=pk)
    form = NiveauAppreciationForm(request.POST or None, instance=niv)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Niveau mis à jour.")
        return redirect("evaluations:admin_bareme")
    return render(request, "evaluations/admin/niveau_form.html", {
        "form": form, "titre": f"Modifier · {niv.libelle}", "objet": niv,
    })


@login_required
@admin_required
def admin_niveau_delete(request, pk):
    niv = get_object_or_404(NiveauAppreciation, pk=pk)
    if request.method == "POST":
        libelle = niv.libelle
        niv.delete()
        messages.success(request, f"Niveau supprimé : {libelle}.")
    return redirect("evaluations:admin_bareme")

