from django.contrib import admin
from apps.content_cms.models import TravelGuide, ResponsibleTravelInitiative, SiteSettings


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'area', 'city', 'updated_at')
    fieldsets = [('Homepage and destination cards', {'fields': ('home_title','home_description','home_eyebrow','home_image_url', 'home_image_alt', 'admin_login_image', 'home_caption', 'home_location', 'nepal_title', 'nepal_description', 'nepal_image', 'beyond_title', 'beyond_description', 'beyond_image')}), ('Explore Treks video preview', {'fields': ('featured_video_title', 'featured_video_description', 'featured_video_thumbnail')}), ('Homepage journey finder options', {'fields': ('home_filter_destinations', 'home_filter_difficulties', 'home_filter_budgets'), 'description': 'Enter one option per line as value|Label. For example: challenging|Challenging.'}), ('Office and map', {'fields': ('city', 'area', 'address', 'map_query', 'map_zoom', 'directions_note')}), ('Journal', {'fields': ('journal_title', 'journal_description', 'featured_story_slug')}), ('Company, partnerships and gallery', {'fields': ('company_title','company_accent','company_content','partner_content','gallery_title','gallery_description','gallery_images')})]

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


from apps.content_cms.models import TrekGuide

@admin.register(TrekGuide)
class TrekGuideAdmin(admin.ModelAdmin):
    list_display = ('name','role','is_published','display_order')
    list_filter = ('is_published',)
    search_fields = ('name','bio')
    filter_horizontal = ('regions','treks_led')
