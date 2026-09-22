from django.contrib import admin
from apps.bookings.models import Booking, DepartureWaitlistEntry, PassengerDetail


class PassengerDetailInline(admin.StackedInline):
    model = PassengerDetail
    extra = 0
    fields = (
        ("full_name", "gender", "date_of_birth"),
        ("passport_number", "passport_expiry_date", "nationality"),
        ("insurance_provider", "insurance_policy_number", "insurance_emergency_phone"),
        ("emergency_contact_name", "emergency_contact_phone"),
        ("dietary_requirements", "medical_conditions"),
    )


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        "booking_reference",
        "customer_name",
        "customer_email",
        "status",
        "payment_type",
        "total_amount_usd",
        "amount_paid_usd",
        "balance_amount_usd",
        "trip_start_date",
        "created_at",
    )
    list_filter = ("status", "payment_type", "trip_start_date")
    search_fields = ("booking_reference", "customer_name", "customer_email")
    readonly_fields = ("booking_reference", "created_at", "updated_at")
    inlines = [PassengerDetailInline]


@admin.register(DepartureWaitlistEntry)
class DepartureWaitlistEntryAdmin(admin.ModelAdmin):
    list_display = (
        "position",
        "customer_name",
        "customer_email",
        "num_travelers",
        "departure",
        "status",
        "offer_expires_at",
    )
    list_filter = ("status", "departure__trip")
    search_fields = ("customer_name", "customer_email", "departure__trip__title")
    readonly_fields = ("position", "offered_at", "offer_expires_at", "created_at", "updated_at")


@admin.register(PassengerDetail)
class PassengerDetailAdmin(admin.ModelAdmin):
    list_display = ("full_name", "nationality", "passport_number", "passport_expiry_date", "booking")
    search_fields = ("full_name", "passport_number", "booking__booking_reference")
    list_filter = ("nationality",)
