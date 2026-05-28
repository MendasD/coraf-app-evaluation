from django.contrib import admin

from .models import (
    Collaborateur,
    Evaluation,
    NiveauAppreciation,
    Objectif,
    ObjectifCatalogue,
)


@admin.register(Collaborateur)
class CollaborateurAdmin(admin.ModelAdmin):
    list_display = ("nom", "prenom", "type", "poste", "direction", "actif")
    list_filter = ("type", "direction", "actif")
    search_fields = ("nom", "prenom", "poste", "projets")


@admin.register(ObjectifCatalogue)
class ObjectifCatalogueAdmin(admin.ModelAdmin):
    list_display = ("ordre", "titre", "coefficient", "actif")
    list_display_links = ("titre",)
    list_editable = ("ordre", "coefficient", "actif")
    list_filter = ("actif",)
    search_fields = ("titre", "description")
    fields = ("ordre", "titre", "description", "livrables", "coefficient", "actif")


class ObjectifInline(admin.TabularInline):
    model = Objectif
    extra = 0
    fields = (
        "numero",
        "titre",
        "coefficient",
        "taux_atteinte",
        "commentaire_evaluateur",
    )
    show_change_link = True


@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = (
        "collaborateur",
        "date_evaluation",
        "statut",
        "note_globale_affichee",
        "appreciation_affichee",
        "date_modification",
    )
    list_filter = ("statut", "date_evaluation", "collaborateur__direction")
    search_fields = ("collaborateur__nom", "collaborateur__prenom")
    date_hierarchy = "date_evaluation"
    inlines = [ObjectifInline]
    autocomplete_fields = ("collaborateur",)

    @admin.display(description="Note globale")
    def note_globale_affichee(self, obj):
        note = obj.note_globale
        return f"{note} %" if note is not None else ""

    @admin.display(description="Appréciation")
    def appreciation_affichee(self, obj):
        appr = obj.appreciation
        return appr.libelle if appr else ""


@admin.register(NiveauAppreciation)
class NiveauAppreciationAdmin(admin.ModelAdmin):
    list_display = ("libelle", "seuil_min", "seuil_max", "couleur")
    ordering = ("-seuil_min",)
