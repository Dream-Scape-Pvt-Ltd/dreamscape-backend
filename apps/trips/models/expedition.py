from django.db import models
from apps.common.models.base import TimeStampedModel


class PeakExpeditionDetail(TimeStampedModel):
    """
    Mountaineering-specific metadata extending standard Trip model.
    """

    trip = models.OneToOneField(
        "trips.Trip",
        on_delete=models.CASCADE,
        related_name="expedition_detail",
    )
    summit_window = models.CharField(max_length=255, blank=True)
    technical_rating = models.CharField(max_length=100, blank=True)
    gear_requirements = models.JSONField(default=list, blank=True)
    permit_fee_type = models.CharField(max_length=100, blank=True)
    mandatory_certifications = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "peak_expedition_details"

    def __str__(self):
        return f"Expedition Details for {self.trip.title}"
