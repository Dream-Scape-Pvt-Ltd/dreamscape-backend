from django.conf import settings
from django.db import models

from .base import TimeStampedModel


class MediaAsset(TimeStampedModel):
    file = models.FileField(upload_to="media/")
    original_name = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=100)
    file_size_bytes = models.PositiveBigIntegerField()
    alt_text = models.CharField(max_length=255, blank=True)
    
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="uploaded_media"
    )

    def __str__(self):
        return self.original_name