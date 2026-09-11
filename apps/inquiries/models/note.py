from django.conf import settings
from django.db import models
from apps.common.models.base import TimeStampedModel


class InquiryNote(TimeStampedModel):
    """
    Internal communication log and consultation notes attached to an inquiry lead.
    """

    inquiry = models.ForeignKey(
        "inquiries.Inquiry",
        on_delete=models.CASCADE,
        related_name="notes",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="inquiry_notes",
    )
    note_text = models.TextField()

    class Meta:
        db_table = "inquiry_notes"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Note by {self.author.email} on {self.inquiry.inquiry_number}"
