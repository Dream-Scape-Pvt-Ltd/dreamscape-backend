from django.contrib import admin
from apps.bookings.models import Booking, PassengerDetail


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


@admin.register(PassengerDetail)
class PassengerDetailAdmin(admin.ModelAdmin):
    list_display = ("full_name", "nationality", "passport_number", "passport_expiry_date", "booking")
    search_fields = ("full_name", "passport_number", "booking__booking_reference")
    list_filter = ("nationality",)
