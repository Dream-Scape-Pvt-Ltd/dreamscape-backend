from django.db import models
from apps.common.models.base import TimeStampedModel

class TrekGuide(TimeStampedModel):
    slug = models.SlugField(max_length=200, unique=True)
    name = models.CharField(max_length=150)
    role = models.CharField(max_length=150, blank=True)
    photo_url = models.CharField(max_length=500, blank=True)
    bio = models.TextField(blank=True)
    years_experience = models.PositiveSmallIntegerField(null=True, blank=True)
    languages = models.JSONField(default=list, blank=True)
    certifications = models.JSONField(default=list, blank=True)
    regions = models.ManyToManyField('destinations.Destination', blank=True, related_name='trek_guides')
    treks_led = models.ManyToManyField('trips.Trip', blank=True, related_name='guides')
    is_published = models.BooleanField(default=False, db_index=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = 'trek_guides'
        ordering = ['display_order','name','id']
