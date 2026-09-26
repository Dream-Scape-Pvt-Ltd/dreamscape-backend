from django.db import models
from apps.common.models.base import TimeStampedModel


class TrekGuide(TimeStampedModel):
    """
    A person who leads Dreamscape treks, shown on the public Guides page.

    Named "trek guide" to keep it apart from TravelGuide, which is a journal
    article. Only published guides are visible to the public.
    """

    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=160, unique=True, db_index=True)
    role = models.CharField(max_length=120, blank=True)
    photo_url = models.URLField(max_length=500, blank=True)
    bio = models.TextField(blank=True)
    years_experience = models.PositiveSmallIntegerField(null=True, blank=True)
    languages = models.JSONField(default=list, blank=True)
    certifications = models.JSONField(default=list, blank=True)
    # Destination.guides is already the reverse name for TravelGuide.
    regions = models.ManyToManyField("destinations.Destination", related_name="trek_guides", blank=True)
    treks_led = models.ManyToManyField("trips.Trip", related_name="trek_guides", blank=True)
    is_published = models.BooleanField(default=False, db_index=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "trek_guides"
        ordering = ["display_order", "name"]
        verbose_name = "Trek guide"
        verbose_name_plural = "Trek guides"

    def __str__(self):
        return self.name
