from django.db import models
from apps.common.models.base import TimeStampedModel


class FAQCategory(models.TextChoices):
    GENERAL = "GENERAL", "General Information"
    BOOKING = "BOOKING", "Booking & Cancellation"
    TREKKING = "TREKKING", "Trekking & Trail Life"
    EXPEDITION = "EXPEDITION", "Peak Climbing & Expeditions"
    PAYMENTS = "PAYMENTS", "Payments & Refunds"


class FAQ(TimeStampedModel):
    """
    Contextual frequently asked question.
    Can attach globally (both null), to a Destination, or to a specific Trip.
    """

    trip = models.ForeignKey(
        "trips.Trip",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="faqs",
    )
    destination = models.ForeignKey(
        "destinations.Destination",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="faqs",
    )
    question = models.CharField(max_length=500)
    answer = models.TextField()
    category = models.CharField(
        max_length=30,
        choices=FAQCategory.choices,
        db_index=True,
    )
    display_order = models.IntegerField(default=0, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "faqs"
        ordering = ["display_order", "id"]
        indexes = [
            models.Index(fields=["trip", "is_active"], name="faq_trip_active_idx"),
            models.Index(fields=["destination", "is_active"], name="faq_dest_active_idx"),
            models.Index(fields=["category", "is_active"], name="faq_cat_active_idx"),
        ]

    def __str__(self):
        target = self.trip.title if self.trip else (self.destination.name if self.destination else "Global")
        return f"[{target}] {self.question}"
