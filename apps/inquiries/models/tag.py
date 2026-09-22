from django.db import models
from apps.common.models.base import TimeStampedModel


class Tag(TimeStampedModel):
    """
    Free-form label for segmenting inquiries (e.g. "budget-sensitive",
    "ebc-interest") used for saved pipeline filters and re-engagement lists.
    """

    name = models.CharField(max_length=50, unique=True)
    color = models.CharField(max_length=7, default="#6B7280")

    class Meta:
        db_table = "crm_tags"
        ordering = ["name"]

    def __str__(self):
        return self.name
