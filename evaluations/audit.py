"""Captation automatique des actions via des signaux Django.

Pour pouvoir lier chaque action à l'utilisateur connecté, on stocke
l'utilisateur courant dans un thread-local via un middleware. Les signaux
le récupèrent ensuite au moment du save/delete.
"""
from threading import local

from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import (
    AuditLog,
    Collaborateur,
    Evaluation,
    NiveauAppreciation,
    ObjectifCatalogue,
    Unite,
)

_local = local()


def set_current_user(user):
    _local.user = user


def get_current_user():
    return getattr(_local, "user", None)


class CurrentUserMiddleware:
    """Middleware qui rend l'utilisateur de la requête accessible aux signaux."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user and getattr(user, "is_authenticated", False):
            set_current_user(user)
        else:
            set_current_user(None)
        try:
            return self.get_response(request)
        finally:
            set_current_user(None)


# === Signaux auto sur modèles clés ==========================================

def _label_for(instance):
    """Libellé court utilisé dans la description du log."""
    return str(instance)[:120]


@receiver(post_save, sender=Collaborateur)
def _log_collaborateur_save(sender, instance, created, **kwargs):
    user = get_current_user()
    action = AuditLog.Action.CREATE if created else AuditLog.Action.UPDATE
    verbe = "ajouté" if created else "modifié"
    AuditLog.log(
        acteur=user,
        action=action,
        description=f"Collaborateur {verbe} : {_label_for(instance)}",
        modele="Collaborateur",
        objet_id=instance.pk,
        cible_user=instance.user,
    )


@receiver(post_delete, sender=Collaborateur)
def _log_collaborateur_delete(sender, instance, **kwargs):
    AuditLog.log(
        acteur=get_current_user(),
        action=AuditLog.Action.DELETE,
        description=f"Collaborateur supprimé : {_label_for(instance)}",
        modele="Collaborateur",
        objet_id=instance.pk,
    )


@receiver(post_save, sender=ObjectifCatalogue)
def _log_catalogue_save(sender, instance, created, **kwargs):
    action = AuditLog.Action.CREATE if created else AuditLog.Action.UPDATE
    verbe = "ajouté au catalogue" if created else "modifié dans le catalogue"
    unite = f" [{instance.unite.libelle}]" if instance.unite_id else ""
    AuditLog.log(
        acteur=get_current_user(),
        action=action,
        description=f"Objectif {verbe}{unite} : {instance.titre[:80]}",
        modele="ObjectifCatalogue",
        objet_id=instance.pk,
    )


@receiver(post_delete, sender=ObjectifCatalogue)
def _log_catalogue_delete(sender, instance, **kwargs):
    AuditLog.log(
        acteur=get_current_user(),
        action=AuditLog.Action.DELETE,
        description=f"Objectif retiré du catalogue : {instance.titre[:80]}",
        modele="ObjectifCatalogue",
        objet_id=instance.pk,
    )


@receiver(post_save, sender=NiveauAppreciation)
def _log_niveau_save(sender, instance, created, **kwargs):
    action = AuditLog.Action.CREATE if created else AuditLog.Action.UPDATE
    verbe = "ajouté" if created else "modifié"
    AuditLog.log(
        acteur=get_current_user(),
        action=action,
        description=f"Niveau d'appréciation {verbe} : {instance.libelle} ({instance.seuil_min}-{instance.seuil_max} %)",
        modele="NiveauAppreciation",
        objet_id=instance.pk,
    )


@receiver(post_delete, sender=NiveauAppreciation)
def _log_niveau_delete(sender, instance, **kwargs):
    AuditLog.log(
        acteur=get_current_user(),
        action=AuditLog.Action.DELETE,
        description=f"Niveau d'appréciation supprimé : {instance.libelle}",
        modele="NiveauAppreciation",
        objet_id=instance.pk,
    )


@receiver(post_save, sender=Unite)
def _log_unite_save(sender, instance, created, **kwargs):
    action = AuditLog.Action.CREATE if created else AuditLog.Action.UPDATE
    verbe = "ajoutée" if created else "modifiée"
    AuditLog.log(
        acteur=get_current_user(),
        action=action,
        description=f"Unité {verbe} : {instance.libelle}",
        modele="Unite",
        objet_id=instance.pk,
    )


User = get_user_model()


@receiver(post_save, sender=User)
def _log_user_save(sender, instance, created, **kwargs):
    user = get_current_user()
    # Si l'acteur est l'utilisateur lui-même (ex. changement de son propre mdp),
    # cible_user = lui ; sinon cible_user = la personne dont le compte a changé.
    if created:
        AuditLog.log(
            acteur=user,
            action=AuditLog.Action.CREATE,
            description=f"Compte utilisateur créé : {instance.email or instance.username}",
            modele="User",
            objet_id=instance.pk,
            cible_user=instance,
        )
    else:
        AuditLog.log(
            acteur=user,
            action=AuditLog.Action.UPDATE,
            description=f"Compte utilisateur modifié : {instance.email or instance.username}",
            modele="User",
            objet_id=instance.pk,
            cible_user=instance,
        )


@receiver(post_delete, sender=Evaluation)
def _log_evaluation_delete(sender, instance, **kwargs):
    AuditLog.log(
        acteur=get_current_user(),
        action=AuditLog.Action.DELETE,
        description=f"Évaluation supprimée : {_label_for(instance)}",
        modele="Evaluation",
        objet_id=instance.pk,
        cible_user=instance.collaborateur.user if instance.collaborateur_id else None,
    )


@receiver(user_logged_in)
def _log_login(sender, request, user, **kwargs):
    AuditLog.log(
        acteur=user,
        action=AuditLog.Action.LOGIN,
        description=f"Connexion : {user.email or user.username}",
        modele="User",
        objet_id=user.pk,
        cible_user=user,
    )
