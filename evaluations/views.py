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
    NiveauAppreciationForm,
    ObjectifCatalogueForm,
    ObjectifCommentaireEvalueFormSet,
    ObjectifForm,
    ObjectifFormSet,
    UtilisateurCreationForm,
    UtilisateurEditForm,
    UtilisateurResetPasswordForm,
)
from .models import (
    Collaborateur,
    Evaluation,
    NiveauAppreciation,
    Objectif,
    ObjectifCatalogue,
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
        return render(request, "evaluations/dashboard_evalue.html", {
            "profil_collab": profil_collab,
            "evaluations": mes_evaluations,
            "Statut": Evaluation.Statut,
        })

    # Sinon : tableau de bord évaluateur / admin classique
    evaluations = (
        Evaluation.objects.select_related("collaborateur")
        .prefetch_related("objectifs")
        .all()
    )
    collaborateurs_qs = Collaborateur.objects.filter(actif=True)
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
        "nb_evaluations": evaluations.count(),
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
    collaborateurs = Collaborateur.objects.annotate(nb_eval=Count("evaluations")).all()
    return render(
        request,
        "evaluations/collaborateur_list.html",
        {"collaborateurs": collaborateurs},
    )


@login_required
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
def evaluation_evalue_edit(request, eval_uuid):
    """Vue restreinte : l'évalué remplit ses parties uniquement."""
    evaluation = get_object_or_404(
        Evaluation.objects.select_related("collaborateur"), uuid=eval_uuid
    )
    # Sécurité : seul l'évalué de cette évaluation (ou un admin) peut y accéder
    if not evaluation.est_evalue(request.user) and not request.user.is_staff:
        messages.error(request, "Vous n'êtes pas autorisé à modifier cette évaluation.")
        return redirect(evaluation.get_absolute_url())

    locked = not evaluation.peut_etre_modifie_par_evalue()

    if request.method == "POST" and locked:
        messages.warning(request, "Cette évaluation a été soumise par l'évaluateur ; vous ne pouvez plus la modifier.")
        return redirect(evaluation.get_absolute_url())

    if request.method == "POST":
        form = EvaluationEvalueForm(request.POST, instance=evaluation)
        formset = ObjectifCommentaireEvalueFormSet(request.POST, instance=evaluation)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, "Vos informations ont été enregistrées.")
            return redirect(evaluation.get_absolute_url())
    else:
        form = EvaluationEvalueForm(instance=evaluation)
        formset = ObjectifCommentaireEvalueFormSet(instance=evaluation)

    return render(request, "evaluations/evaluation_evalue_form.html", {
        "evaluation": evaluation,
        "form": form,
        "formset": formset,
        "objectifs": list(evaluation.objectifs.all()),
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
        evaluation.statut = target
        evaluation.save(update_fields=["statut"])
        labels = dict(Evaluation.Statut.choices)
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
            messages.success(
                request,
                f"Mot de passe réinitialisé. Nouveau mot de passe : {form.cleaned_data['password']} (à transmettre)."
            )
    return redirect("evaluations:admin_utilisateur_edit", pk=utilisateur.pk)


# --- Catalogue d'objectifs -------------------------------------------------

@login_required
@admin_required
def admin_catalogue(request):
    objectifs = ObjectifCatalogue.objects.all().order_by("ordre", "id")
    return render(request, "evaluations/admin/catalogue_list.html", {"objectifs": objectifs})


@login_required
@admin_required
def admin_objectif_create(request):
    form = ObjectifCatalogueForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Objectif ajouté au catalogue.")
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

