from django.contrib import admin
from apps.content_cms.models import SiteSettings, TravelGuide, ResponsibleTravelInitiative, TrekGuide


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ("__str__", "crm_sla_hours", "updated_at")

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TravelGuide)
class TravelGuideAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "country", "destination", "is_published", "published_at")
    list_filter = ("category", "is_published", "country")
    search_fields = ("title", "markdown_content", "meta_title")
    prepopulated_fields = {"slug": ("title",)}


@admin.register(ResponsibleTravelInitiative)
class ResponsibleTravelInitiativeAdmin(admin.ModelAdmin):
    list_display = ("title", "is_published", "created_at")
    list_filter = ("is_published",)
    search_fields = ("title", "content")
    prepopulated_fields = {"slug": ("title",)}


@admin.register(TrekGuide)
class TrekGuideAdmin(admin.ModelAdmin):
    list_display = ("name", "role", "years_experience", "is_published", "display_order")
    list_filter = ("is_published",)
    search_fields = ("name", "role", "bio")
    filter_horizontal = ("regions", "treks_led")
    prepopulated_fields = {"slug": ("name",)}
