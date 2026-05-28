"""Authentification par email (au lieu du nom d'utilisateur Django par défaut)."""
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

UserModel = get_user_model()


class EmailBackend(ModelBackend):
    """Cherche l'utilisateur par email puis vérifie le mot de passe.

    Permet de se connecter via email même si le modèle Django par défaut
    stocke un `username`. On garde le `username` en interne mais il n'est
    plus exposé à l'utilisateur.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        email = (username or kwargs.get("email") or "").strip().lower()
        if not email or password is None:
            return None
        try:
            user = UserModel.objects.get(email__iexact=email)
        except UserModel.DoesNotExist:
            # Cas de secours : un superuser créé via createsuperuser n'a peut-être
            # pas d'email ; on autorise alors une connexion via username pour le
            # tout premier admin.
            try:
                user = UserModel.objects.get(username=email)
            except UserModel.DoesNotExist:
                return None
        except UserModel.MultipleObjectsReturned:
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
