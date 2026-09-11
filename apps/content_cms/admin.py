from django.contrib import admin
from apps.content_cms.models import TravelGuide, ResponsibleTravelInitiative


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
