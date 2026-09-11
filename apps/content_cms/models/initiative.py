from django.db import models
from apps.common.models.base import TimeStampedModel


class ResponsibleTravelInitiative(TimeStampedModel):
    """
    Porter welfare pledges, carbon offset documentation, and leave-no-trace commitments.
    """

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    pillars = models.JSONField(
        default=list,
        blank=True,
        help_text="e.g. Community Support, Porter Welfare, Environmental Protection, Waste Management",
    )
    content = models.TextField()
    is_published = models.BooleanField(default=False, db_index=True)

    class Meta:
        db_table = "responsible_travel_initiatives"
        ordering = ["title"]

    def __str__(self):
        return self.title
