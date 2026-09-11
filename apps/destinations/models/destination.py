from django.db import models
from apps.common.models.base import TimeStampedModel


class DestinationCountry(models.TextChoices):
    NEPAL = "NEPAL", "Nepal"
    TIBET = "TIBET", "Tibet"
    BHUTAN = "BHUTAN", "Bhutan"
    INDIA = "INDIA", "India"
    MULTI_COUNTRY = "MULTI_COUNTRY", "Multi Country"


class Destination(TimeStampedModel):
    """
    Geographic destination and regional hub for trekking, expeditions, and cultural tours.
    """

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, db_index=True)
    country = models.CharField(
        max_length=30,
        choices=DestinationCountry.choices,
        db_index=True,
    )
    region_name = models.CharField(max_length=150, blank=True)
    visa_guidelines = models.TextField(blank=True)
    permit_details = models.TextField(blank=True)
    hero_media = models.URLField(max_length=500, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "destinations"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["country", "is_active"], name="dest_country_active_idx"),
        ]

    def __str__(self):
        return f"{self.name} ({self.country})"
