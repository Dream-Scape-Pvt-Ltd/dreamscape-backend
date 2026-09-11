from django.db import models
from apps.common.models.base import TimeStampedModel


class ActivityCategory(TimeStampedModel):
    """
    Activity categorization for trips (e.g. Trekking, Mountaineering, Cultural, Wildlife).
    """

    name = models.CharField(max_length=150, unique=True)
    slug = models.SlugField(max_length=150, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "activity_categories"
        ordering = ["name"]
        verbose_name_plural = "Activity Categories"

    def __str__(self):
        return self.name
