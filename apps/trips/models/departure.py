from django.db import models
from django.db.models import F, Q
from apps.common.models.base import TimeStampedModel


class DepartureStatus(models.TextChoices):
    GUARANTEED = "GUARANTEED", "Guaranteed Departure"
    LIMITED = "LIMITED", "Limited Availability"
    SOLD_OUT = "SOLD_OUT", "Sold Out"
    WAITLIST = "WAITLIST", "Waitlist Only"
    CANCELLED = "CANCELLED", "Cancelled"


class AvailabilityState(models.TextChoices):
    """
    Derived, client-facing availability indicator.

    Distinct from ``status``, which is the admin-managed lifecycle field: an
    admin may pin ``status`` (see ``status_locked``) while this stays an honest
    reflection of the seat ledger for public display.
    """

    AVAILABLE = "AVAILABLE", "Available"
    FEW_SEATS_LEFT = "FEW_SEATS_LEFT", "Few Seats Left"
    SOLD_OUT = "SOLD_OUT", "Sold Out"
    WAITLIST = "WAITLIST", "Waitlist"
    CANCELLED = "CANCELLED", "Cancelled"


#: Seats still bookable, as a database expression. ``available_seats`` is a
#: Python property, so anything filtering or ordering in SQL must use this.
AVAILABLE_SEATS_EXPR = F("max_seats") - F("reserved_seats") - F("booked_seats")


class TripDepartureQuerySet(models.QuerySet):
    def with_availability(self):
        """Annotate ``seats_left`` so availability can be filtered/ordered in SQL."""
        return self.annotate(
            seats_left=models.ExpressionWrapper(
                AVAILABLE_SEATS_EXPR,
                output_field=models.IntegerField(),
            )
        )

    def bookable(self):
        """Departures a customer can still book a seat on today."""
        return self.with_availability().filter(seats_left__gt=0).exclude(
            status__in=[
                DepartureStatus.SOLD_OUT,
                DepartureStatus.WAITLIST,
                DepartureStatus.CANCELLED,
            ]
        )

    def with_capacity_counts(self):
        """
        Annotate live demand alongside the seat ledger: open leads and people
        waiting. Aggregated in one query rather than per row, since the admin
        capacity board lists many departures at once.

        ``distinct=True`` is required — the two joins multiply each other's rows.
        """
        from apps.bookings.models import WaitlistStatus
        from apps.inquiries.models import InquiryStatus

        open_lead_statuses = [
            InquiryStatus.NEW,
            InquiryStatus.ASSIGNED,
            InquiryStatus.IN_CONTACT,
        ]
        return self.with_availability().annotate(
            open_inquiry_count=models.Count(
                "inquiries",
                filter=Q(inquiries__status__in=open_lead_statuses),
                distinct=True,
            ),
            waitlisted_count=models.Count(
                "waitlist_entries",
                filter=Q(waitlist_entries__status=WaitlistStatus.WAITING),
                distinct=True,
            ),
        )


class TripDeparture(TimeStampedModel):
    """
    Fixed-date scheduled departure for small group departures.

    Seat inventory is a ledger with a single mutable counter: ``booked_seats``
    is the only field the booking flow writes. ``reserved_seats`` is an admin
    held-back block, and ``available_seats`` is derived from the two. Keeping
    one writable counter is what makes the numbers unable to drift apart.
    """

    trip = models.ForeignKey(
        "trips.Trip",
        on_delete=models.PROTECT,
        related_name="departures",
    )
    start_date = models.DateField(db_index=True)
    end_date = models.DateField(db_index=True)
    price_usd = models.DecimalField(max_digits=12, decimal_places=2)
    max_seats = models.PositiveIntegerField()
    booked_seats = models.PositiveIntegerField(
        default=0,
        help_text="Seats consumed by bookings. The only counter the booking flow mutates.",
    )
    reserved_seats = models.PositiveIntegerField(
        default=0,
        help_text="Seats held back by an admin (staff, guides, agent allotment). Not bookable.",
    )
    few_seats_threshold = models.PositiveIntegerField(
        default=3,
        help_text="At or below this many available seats the departure reads as 'Few Seats Left'.",
    )
    waitlist_enabled = models.BooleanField(
        default=True,
        help_text="Whether a full departure accepts waitlist entries.",
    )
    status_locked = models.BooleanField(
        default=False,
        help_text="Pin the admin-chosen status; automatic recomputation leaves it alone.",
    )
    status = models.CharField(
        max_length=20,
        choices=DepartureStatus.choices,
        default=DepartureStatus.LIMITED,
        db_index=True,
    )
    is_guaranteed = models.BooleanField(default=False)

    objects = TripDepartureQuerySet.as_manager()

    class Meta:
        db_table = "trip_departures"
        ordering = ["start_date"]
        constraints = [
            models.CheckConstraint(
                condition=Q(booked_seats__lte=F("max_seats") - F("reserved_seats")),
                name="valid_departure_seats",
            ),
            models.CheckConstraint(
                condition=Q(reserved_seats__lte=F("max_seats")),
                name="valid_departure_reserved_seats",
            ),
            models.CheckConstraint(
                condition=Q(end_date__gte=F("start_date")),
                name="valid_departure_dates",
            ),
        ]
        indexes = [
            models.Index(fields=["trip", "start_date"], name="dep_trip_start_idx"),
            models.Index(fields=["status", "start_date"], name="dep_status_start_idx"),
        ]

    # -- Derived seat figures -------------------------------------------------

    @property
    def available_seats(self) -> int:
        """Bookable seats remaining. Floored at 0 so a shrunk max never reads negative."""
        return max(self.max_seats - self.reserved_seats - self.booked_seats, 0)

    @property
    def utilization_pct(self) -> int:
        if not self.max_seats:
            return 0
        return round((self.booked_seats + self.reserved_seats) * 100 / self.max_seats)

    @property
    def availability_state(self) -> str:
        if self.status == DepartureStatus.CANCELLED:
            return AvailabilityState.CANCELLED
        available = self.available_seats
        if available <= 0:
            return (
                AvailabilityState.WAITLIST
                if self.waitlist_enabled
                else AvailabilityState.SOLD_OUT
            )
        if available <= self.few_seats_threshold:
            return AvailabilityState.FEW_SEATS_LEFT
        return AvailabilityState.AVAILABLE

    # -- Status ---------------------------------------------------------------

    def recompute_status(self) -> bool:
        """
        Realign ``status`` with the seat ledger.

        Returns True when the value changed, so callers can keep their
        ``update_fields`` tight. A cancelled or admin-pinned departure is left
        untouched.
        """
        if self.status_locked or self.status == DepartureStatus.CANCELLED:
            return False

        available = self.available_seats
        if available <= 0:
            new_status = (
                DepartureStatus.WAITLIST
                if self.waitlist_enabled
                else DepartureStatus.SOLD_OUT
            )
        elif available <= self.few_seats_threshold:
            new_status = DepartureStatus.LIMITED
        else:
            new_status = (
                DepartureStatus.GUARANTEED
                if self.is_guaranteed
                else DepartureStatus.LIMITED
            )

        if new_status == self.status:
            return False
        self.status = new_status
        return True

    def __str__(self):
        return f"{self.trip.title}: {self.start_date} -> {self.end_date} ({self.available_seats}/{self.max_seats} left)"
