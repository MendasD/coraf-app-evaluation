from django.urls import path

from . import views

app_name = "evaluations"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),

    path("collaborateurs/", views.collaborateur_list, name="collaborateur_list"),
    path("collaborateurs/nouveau/", views.collaborateur_create, name="collaborateur_create"),
    path("collaborateurs/<uuid:collab_uuid>/", views.collaborateur_detail, name="collaborateur_detail"),
    path("collaborateurs/<uuid:collab_uuid>/modifier/", views.collaborateur_edit, name="collaborateur_edit"),

    path("evaluations/nouvelle/", views.evaluation_create, name="evaluation_create"),
    path("evaluations/demarrer/", views.evaluation_start, name="evaluation_start"),
    path("evaluations/<uuid:eval_uuid>/", views.evaluation_detail, name="evaluation_detail"),
    path("evaluations/<uuid:eval_uuid>/modifier/", views.evaluation_edit, name="evaluation_edit"),
    path("evaluations/<uuid:eval_uuid>/ma-saisie/", views.evaluation_evalue_edit, name="evaluation_evalue_edit"),
    path("evaluations/<uuid:eval_uuid>/statut/", views.evaluation_change_statut, name="evaluation_change_statut"),
    path("evaluations/<uuid:eval_uuid>/imprimer/", views.evaluation_print, name="evaluation_print"),
    path("evaluations/<uuid:eval_uuid>/supprimer/", views.evaluation_delete, name="evaluation_delete"),

    # Mon compte (édition de son propre profil utilisateur)
    path("mon-compte/", views.mon_compte, name="mon_compte"),

    # Journal d'audit (visible par tous, contenu filtré selon le rôle)
    path("journal/", views.audit_log, name="audit_log"),
    path("journal/vider/", views.audit_log_clear, name="audit_log_clear"),

    # Espace administration in-app (réservé aux is_staff)
    path("administration/", views.admin_home, name="admin_home"),
    path("administration/statistiques/", views.admin_statistiques, name="admin_statistiques"),
    path("administration/utilisateurs/", views.admin_utilisateurs, name="admin_utilisateurs"),
    path("administration/utilisateurs/nouveau/", views.admin_utilisateur_create, name="admin_utilisateur_create"),
    path("administration/utilisateurs/<int:pk>/", views.admin_utilisateur_edit, name="admin_utilisateur_edit"),
    path("administration/utilisateurs/<int:pk>/reset-mdp/", views.admin_utilisateur_reset_password, name="admin_utilisateur_reset_password"),

    path("administration/catalogue/", views.admin_catalogue, name="admin_catalogue"),
    path("administration/catalogue/nouveau/", views.admin_objectif_create, name="admin_objectif_create"),
    path("administration/catalogue/<int:pk>/", views.admin_objectif_edit, name="admin_objectif_edit"),
    path("administration/catalogue/<int:pk>/supprimer/", views.admin_objectif_delete, name="admin_objectif_delete"),

    path("administration/bareme/", views.admin_bareme, name="admin_bareme"),
    path("administration/bareme/nouveau/", views.admin_niveau_create, name="admin_niveau_create"),
    path("administration/bareme/<int:pk>/", views.admin_niveau_edit, name="admin_niveau_edit"),
    path("administration/bareme/<int:pk>/supprimer/", views.admin_niveau_delete, name="admin_niveau_delete"),
]
