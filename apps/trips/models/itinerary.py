from django.db import models
from apps.common.models.base import TimeStampedModel


class AccommodationType(models.TextChoices):
    TEAHOUSE = "TEAHOUSE", "Teahouse / Lodge"
    CAMPING = "CAMPING", "Tented Camp"
    HOTEL = "HOTEL", "Hotel"
    LODGE = "LODGE", "Luxury Lodge"
    HOMESTAY = "HOMESTAY", "Homestay"


class ItineraryDay(TimeStampedModel):
    """
    Day-by-day trail breakdown with elevation profile and geographical coordinates.
    """

    trip = models.ForeignKey(
        "trips.Trip",
        on_delete=models.CASCADE,
        related_name="itinerary_days",
    )
    day_number = models.PositiveIntegerField()
    title = models.CharField(max_length=255)
    description = models.TextField()
    overnight_stay = models.CharField(max_length=255, blank=True)
    elevation_meters = models.IntegerField(null=True, blank=True)
    accommodation_type = models.CharField(
        max_length=30,
        choices=AccommodationType.choices,
        default=AccommodationType.TEAHOUSE,
    )
    is_acclimatization_day = models.BooleanField(default=False)
    meals_included = models.JSONField(default=list, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)

    class Meta:
        db_table = "itinerary_days"
        ordering = ["day_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["trip", "day_number"],
                name="unique_trip_day_number",
            )
        ]

    def __str__(self):
        return f"Day {self.day_number}: {self.title} ({self.trip.title})"
