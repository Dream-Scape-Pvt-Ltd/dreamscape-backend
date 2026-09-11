from django.contrib import admin
from apps.destinations.models import Destination, ActivityCategory


@admin.register(Destination)
class DestinationAdmin(admin.ModelAdmin):
    list_display = ("name", "country", "region_name", "is_active", "created_at")
    list_filter = ("country", "is_active")
    search_fields = ("name", "region_name")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(ActivityCategory)
class ActivityCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
