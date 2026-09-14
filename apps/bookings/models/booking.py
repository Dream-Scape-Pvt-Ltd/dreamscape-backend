from django.conf import settings
from django.db import models
from django.db.models import Q
from apps.common.models.base import TimeStampedModel


class PaymentType(models.TextChoices):
    FULL_100 = "FULL_100", "100% Full Payment"
    DEPOSIT_20 = "DEPOSIT_20", "20% Deposit"


class BookingStatus(models.TextChoices):
    PENDING = "PENDING", "Pending Confirmation"
    DEPOSIT_PAID = "DEPOSIT_PAID", "Deposit Paid (20%)"
    FULLY_PAID = "FULLY_PAID", "Fully Paid"
    CANCELLED = "CANCELLED", "Cancelled"
    REFUNDED = "REFUNDED", "Refunded"


class Booking(TimeStampedModel):
    """
    Trek and expedition booking record.
    Enforces financial constraints at database level to prevent negative or corrupt balances.
    """

    booking_reference = models.CharField(
        max_length=30,
        unique=True,
        db_index=True,
    )
    customer_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bookings",
    )
    departure = models.ForeignKey(
        "trips.TripDeparture",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="bookings",
    )
    custom_trip = models.ForeignKey(
        "trips.Trip",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="custom_bookings",
    )
    customer_name = models.CharField(max_length=255)
    customer_email = models.EmailField(db_index=True)
    customer_phone = models.CharField(max_length=50, blank=True)
    num_travelers = models.PositiveIntegerField(default=1)
    total_amount_usd = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default="USD")
    payment_type = models.CharField(
        max_length=20,
        choices=PaymentType.choices,
        default=PaymentType.DEPOSIT_20,
    )
    deposit_amount_usd = models.DecimalField(max_digits=12, decimal_places=2)
    balance_amount_usd = models.DecimalField(max_digits=12, decimal_places=2)
    amount_paid_usd = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(
        max_length=20,
        choices=BookingStatus.choices,
        default=BookingStatus.PENDING,
        db_index=True,
    )
    trip_start_date = models.DateField(db_index=True)
    balance_due_date = models.DateField(null=True, blank=True, db_index=True)
    cancellation_reason = models.TextField(blank=True, default="")

    class Meta:
        db_table = "bookings"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(total_amount_usd__gt=0),
                name="positive_total_amount",
            ),
            models.CheckConstraint(
                condition=Q(amount_paid_usd__gte=0),
                name="non_negative_amount_paid",
            ),
            models.CheckConstraint(
                condition=Q(deposit_amount_usd__gte=0),
                name="non_negative_deposit",
            ),
            models.CheckConstraint(
                condition=Q(balance_amount_usd__gte=0),
                name="non_negative_balance",
            ),
            models.CheckConstraint(
                condition=Q(num_travelers__gte=1),
                name="minimum_one_traveler",
            ),
        ]
        indexes = [
            models.Index(fields=["customer_email", "status"], name="book_email_status_idx"),
            models.Index(fields=["status", "trip_start_date"], name="book_status_date_idx"),
        ]

    def __str__(self):
        return f"{self.booking_reference} - {self.customer_name} ({self.status})"
