from django.contrib import admin
from apps.content_cms.models import TravelGuide, ResponsibleTravelInitiative, SiteSettings


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'area', 'city', 'updated_at')
    fieldsets = [('Homepage photograph', {'fields': ('home_image_url', 'home_image_alt')}), ('Office and map', {'fields': ('city', 'area', 'address', 'map_query', 'map_zoom', 'directions_note')}), ('Journal', {'fields': ('journal_title', 'journal_description', 'featured_story_slug')})]

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists() and super().has_add_permission(request)

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
