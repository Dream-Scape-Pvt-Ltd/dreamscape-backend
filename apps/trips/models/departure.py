from django.db import models
from django.db.models import F, Q
from apps.common.models.base import TimeStampedModel


class DepartureStatus(models.TextChoices):
    GUARANTEED = "GUARANTEED", "Guaranteed Departure"
    LIMITED = "LIMITED", "Limited Availability"
    SOLD_OUT = "SOLD_OUT", "Sold Out"
    CANCELLED = "CANCELLED", "Cancelled"


class TripDeparture(TimeStampedModel):
    """
    Fixed-date scheduled departure for small group departures.
    Protected by database-level seat bounds and date integrity constraints.
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
    available_seats = models.PositiveIntegerField()
    status = models.CharField(
        max_length=20,
        choices=DepartureStatus.choices,
        default=DepartureStatus.LIMITED,
        db_index=True,
    )
    is_guaranteed = models.BooleanField(default=False)

    class Meta:
        db_table = "trip_departures"
        ordering = ["start_date"]
        constraints = [
            models.CheckConstraint(
                condition=Q(available_seats__gte=0) & Q(available_seats__lte=F("max_seats")),
                name="valid_departure_seats",
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

    def __str__(self):
        return f"{self.trip.title}: {self.start_date} -> {self.end_date} ({self.available_seats}/{self.max_seats} left)"
