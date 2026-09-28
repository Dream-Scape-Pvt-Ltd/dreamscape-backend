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
    headline = models.CharField(max_length=180, blank=True)
    description = models.TextField(blank=True)
    highlights = models.CharField(max_length=400, blank=True)
    trail_style = models.CharField(max_length=200, blank=True)
    pace = models.CharField(max_length=200, blank=True)
    base = models.CharField(max_length=150, blank=True)
    mood = models.CharField(max_length=30, blank=True)
    visa_guidelines = models.TextField(blank=True)
    permit_details = models.TextField(blank=True)
    hero_media = models.URLField(max_length=500, blank=True)
    gallery_images = models.JSONField(
        default=list,
        blank=True,
        help_text="Additional destination photo URLs, in display order (JSON array).",
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "destinations"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["country", "is_active"], name="dest_country_active_idx"),
        ]

    def __str__(self):
        return f"{self.name} ({self.country})"
