from django.contrib import admin
from apps.trips.models import (
    Trip,
    PeakExpeditionDetail,
    ItineraryDay,
    TripDeparture,
    TripReview,
)


class ItineraryDayInline(admin.TabularInline):
    model = ItineraryDay
    extra = 1
    fields = ("day_number", "title", "elevation_meters", "accommodation_type", "is_acclimatization_day")
    ordering = ("day_number",)


class TripDepartureInline(admin.TabularInline):
    model = TripDeparture
    extra = 1
    fields = ("start_date", "end_date", "price_usd", "max_seats", "available_seats", "status", "is_guaranteed")


class PeakExpeditionDetailInline(admin.StackedInline):
    model = PeakExpeditionDetail
    can_delete = False
    max_num = 1


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = ("title", "destination", "category", "duration_days", "difficulty_grade", "starting_price_usd", "is_featured", "is_active")
    list_filter = ("destination", "category", "difficulty_grade", "is_featured", "is_active")
    search_fields = ("title", "overview")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [PeakExpeditionDetailInline, ItineraryDayInline, TripDepartureInline]


@admin.register(TripDeparture)
class TripDepartureAdmin(admin.ModelAdmin):
    list_display = ("trip", "start_date", "end_date", "price_usd", "available_seats", "max_seats", "status", "is_guaranteed")
    list_filter = ("status", "is_guaranteed", "start_date")
    search_fields = ("trip__title",)


@admin.register(TripReview)
class TripReviewAdmin(admin.ModelAdmin):
    list_display = ("reviewer_name", "trip", "rating_overall", "is_verified", "is_published", "created_at")
    list_filter = ("rating_overall", "is_verified", "is_published", "created_at")
    search_fields = ("reviewer_name", "title", "content", "trip__title")
