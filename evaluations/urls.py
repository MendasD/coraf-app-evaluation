from django.urls import path

from . import views

app_name = "evaluations"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),

    path("collaborateurs/", views.collaborateur_list, name="collaborateur_list"),
    path("collaborateurs/nouveau/", views.collaborateur_create, name="collaborateur_create"),
    path("collaborateurs/<uuid:collab_uuid>/", views.collaborateur_detail, name="collaborateur_detail"),

    path("evaluations/nouvelle/", views.evaluation_create, name="evaluation_create"),
    path("evaluations/<uuid:eval_uuid>/", views.evaluation_detail, name="evaluation_detail"),
    path("evaluations/<uuid:eval_uuid>/modifier/", views.evaluation_edit, name="evaluation_edit"),
    path("evaluations/<uuid:eval_uuid>/ma-saisie/", views.evaluation_evalue_edit, name="evaluation_evalue_edit"),
    path("evaluations/<uuid:eval_uuid>/statut/", views.evaluation_change_statut, name="evaluation_change_statut"),
    path("evaluations/<uuid:eval_uuid>/imprimer/", views.evaluation_print, name="evaluation_print"),

    # Espace administration in-app (réservé aux is_staff)
    path("administration/", views.admin_home, name="admin_home"),
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
