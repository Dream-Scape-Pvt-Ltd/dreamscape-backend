from django.contrib import admin
from apps.destinations.models import Destination, ActivityCategory, NavigationMenu


@admin.register(NavigationMenu)
class NavigationMenuAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "menu_type", "sort_order", "is_active")
    list_filter = ("menu_type", "is_active")


@admin.register(Destination)
class DestinationAdmin(admin.ModelAdmin):
    list_display = ("name", "country", "region_name", "is_active", "created_at")
    list_filter = ("country", "is_active")
    search_fields = ("name", "region_name")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(ActivityCategory)
class ActivityCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "menu", "is_active", "created_at")
    list_filter = ("menu", "is_active")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
