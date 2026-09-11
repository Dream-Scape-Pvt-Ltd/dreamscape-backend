from django.contrib import admin
from apps.payments.models import PaymentTransaction, PaymentActionToken


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "transaction_id",
        "booking",
        "gateway",
        "payment_stage",
        "amount",
        "currency",
        "status",
        "processed_at",
        "created_at",
    )
    list_filter = ("gateway", "payment_stage", "status", "currency")
    search_fields = ("transaction_id", "booking__booking_reference", "idempotency_key")
    readonly_fields = ("created_at", "updated_at")


@admin.register(PaymentActionToken)
class PaymentActionTokenAdmin(admin.ModelAdmin):
    list_display = ("booking", "purpose", "expires_at", "used_at", "created_at")
    list_filter = ("purpose", "expires_at")
    search_fields = ("booking__booking_reference", "token_hash")
