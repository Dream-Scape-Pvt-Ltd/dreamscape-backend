from django.conf import settings
from django.db import models
from django.db.models import Q
from apps.common.models.base import TimeStampedModel


class WaitlistStatus(models.TextChoices):
    WAITING = "WAITING", "Waiting"
    OFFERED = "OFFERED", "Seat Offered"
    CONVERTED = "CONVERTED", "Converted to Booking"
    EXPIRED = "EXPIRED", "Offer Expired"
    CANCELLED = "CANCELLED", "Cancelled"


class DepartureWaitlistEntry(TimeStampedModel):
    """
    Demand captured against a full departure.

    Lives with bookings rather than the trip catalog because an entry carries
    customer contact details and is promoted into a Booking. Entries are served
    in ``position`` order; a freed seat offers the head of the queue a
    time-limited claim rather than booking it outright.
    """

    departure = models.ForeignKey(
        "trips.TripDeparture",
        on_delete=models.PROTECT,
        related_name="waitlist_entries",
    )
    customer_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="waitlist_entries",
    )
    source_inquiry = models.ForeignKey(
        "inquiries.Inquiry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="waitlist_entries",
    )
    converted_booking = models.OneToOneField(
        "bookings.Booking",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_waitlist_entry",
    )

    customer_name = models.CharField(max_length=255)
    customer_email = models.EmailField(db_index=True)
    customer_phone = models.CharField(max_length=50, blank=True, default="")
    num_travelers = models.PositiveIntegerField(default=1)

    position = models.PositiveIntegerField(
        help_text="Queue position, 1-based. Lower is served first.",
    )
    status = models.CharField(
        max_length=20,
        choices=WaitlistStatus.choices,
        default=WaitlistStatus.WAITING,
        db_index=True,
    )
    offered_at = models.DateTimeField(null=True, blank=True)
    offer_expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "departure_waitlist_entries"
        ordering = ["departure", "position"]
        constraints = [
            # One live entry per email per departure. Scoped to WAITING so a
            # traveller whose earlier offer expired can rejoin the queue.
            models.UniqueConstraint(
                fields=["departure", "customer_email"],
                condition=Q(status="WAITING"),
                name="unique_active_waitlist_entry",
            ),
            models.CheckConstraint(
                condition=Q(num_travelers__gte=1),
                name="waitlist_minimum_one_traveler",
            ),
        ]
        indexes = [
            models.Index(fields=["departure", "position"], name="wait_dep_position_idx"),
            models.Index(fields=["status", "offer_expires_at"], name="wait_status_expiry_idx"),
        ]

    def __str__(self):
        return f"#{self.position} {self.customer_email} -> {self.departure_id} ({self.status})"
