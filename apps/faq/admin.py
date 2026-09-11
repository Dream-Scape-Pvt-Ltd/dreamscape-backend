from django.contrib import admin
from apps.faq.models import FAQ


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ("question", "category", "trip", "destination", "display_order", "is_active")
    list_filter = ("category", "is_active", "destination")
    search_fields = ("question", "answer")
    ordering = ("display_order", "id")
