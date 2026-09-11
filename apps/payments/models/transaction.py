from django.db import models
from apps.common.models.base import TimeStampedModel


class PaymentGateway(models.TextChoices):
    KHALTI = "KHALTI", "Khalti (Nepal / International Cards)"
    STRIPE = "STRIPE", "Stripe (Global Credit Cards)"
    BANK = "BANK", "Direct Wire / SWIFT Transfer"


class PaymentStage(models.TextChoices):
    DEPOSIT_20 = "DEPOSIT_20", "20% Deposit"
    BALANCE_80 = "BALANCE_80", "80% Balance"
    FULL_100 = "FULL_100", "100% Full Payment"
    CUSTOM_ADJUSTMENT = "CUSTOM_ADJUSTMENT", "Custom Adjustment"
    REFUND = "REFUND", "Refund"


class PaymentStatus(models.TextChoices):
    INITIATED = "INITIATED", "Initiated"
    SUCCESS = "SUCCESS", "Success"
    FAILED = "FAILED", "Failed"
    REFUNDED = "REFUNDED", "Refunded"


class PaymentTransaction(TimeStampedModel):
    """
    Financial payment record linking external payment gateway transactions to bookings.
    Protected from accidental deletion by models.PROTECT.
    """

    booking = models.ForeignKey(
        "bookings.Booking",
        on_delete=models.PROTECT,
        related_name="payments",
    )
    transaction_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
    )
    idempotency_key = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
    )
    gateway = models.CharField(
        max_length=20,
        choices=PaymentGateway.choices,
        db_index=True,
    )
    payment_stage = models.CharField(
        max_length=20,
        choices=PaymentStage.choices,
        db_index=True,
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default="USD")
    exchange_rate = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
    )
    charged_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
    )
    charged_currency = models.CharField(max_length=10, default="NPR")
    gateway_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.INITIATED,
        db_index=True,
    )
    webhook_raw_payload = models.JSONField(default=dict, blank=True)
    webhook_event_id = models.CharField(max_length=255, blank=True, db_index=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "payment_transactions"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["booking", "status"], name="pay_book_status_idx"),
            models.Index(fields=["gateway", "status"], name="pay_gateway_status_idx"),
        ]

    def __str__(self):
        return f"{self.gateway} {self.transaction_id} - {self.amount} {self.currency} ({self.status})"
