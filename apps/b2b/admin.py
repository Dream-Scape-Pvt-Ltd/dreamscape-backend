from django.contrib import admin
from django import forms
from django.db import models
from apps.b2b.models import B2BPartner, B2BAsset, B2BBooking


@admin.register(B2BPartner)
class B2BPartnerAdmin(admin.ModelAdmin):
    list_display = ("company_name", "user", "country", "agency_tier", "commission_rate", "approved", "created_at")
    list_filter = ("agency_tier", "approved", "country")
    search_fields = ("company_name", "user__email", "country")


@admin.register(B2BAsset)
class B2BAssetAdmin(admin.ModelAdmin):
    # The standard ClearableFileInput accesses file.url, forbidden for private storage.
    formfield_overrides = {models.FileField: {'widget': forms.FileInput}}
    list_display = ("title", "asset_type", "trip", "minimum_tier", "is_active", "created_at")
    list_filter = ("asset_type", "minimum_tier", "is_active")
    search_fields = ("title", "trip__title")


@admin.register(B2BBooking)
class B2BBookingAdmin(admin.ModelAdmin):
    list_display = (
        "partner",
        "booking",
        "gross_amount_usd",
        "commission_rate",
        "commission_amount_usd",
        "net_amount_usd",
        "commission_status",
    )
    list_filter = ("commission_status",)
    search_fields = ("partner__company_name", "booking__booking_reference")
