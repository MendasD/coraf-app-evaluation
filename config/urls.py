from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from evaluations.forms import EmailAuthenticationForm

urlpatterns = [
    # Authentification
    path("connexion/", auth_views.LoginView.as_view(
        template_name="auth/login.html",
        authentication_form=EmailAuthenticationForm,
        redirect_authenticated_user=True,
    ), name="login"),
    path("deconnexion/", auth_views.LogoutView.as_view(), name="logout"),
    path("mot-de-passe/", auth_views.PasswordChangeView.as_view(
        template_name="auth/password_change.html",
        success_url="/mot-de-passe/ok/",
    ), name="password_change"),
    path("mot-de-passe/ok/", auth_views.PasswordChangeDoneView.as_view(
        template_name="auth/password_change_done.html",
    ), name="password_change_done"),

    # Portail Django admin (filet de sécurité, plus en avant dans l'UI)
    path("django-admin/", admin.site.urls),

    # App
    path("", include("evaluations.urls")),
]
