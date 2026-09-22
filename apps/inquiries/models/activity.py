from django.conf import settings
from django.db import models
from apps.common.models.base import TimeStampedModel


class ActivityChannel(models.TextChoices):
    CALL = "CALL", "Phone Call"
    EMAIL = "EMAIL", "Email"
    WHATSAPP = "WHATSAPP", "WhatsApp"
    NOTE = "NOTE", "Internal Note"
    STATUS_CHANGE = "STATUS_CHANGE", "Status Change"
    SYSTEM = "SYSTEM", "System Event"

# Channels that count as an agent having actually reached out to the lead,
# used to stamp Inquiry.first_response_at.
OUTREACH_CHANNELS = (ActivityChannel.CALL, ActivityChannel.EMAIL, ActivityChannel.WHATSAPP)


class Activity(TimeStampedModel):
    """
    Structured CRM timeline entry for an inquiry: a logged call, email,
    WhatsApp touch, status transition, or system event. Complements the
    free-text InquiryNote thread rather than replacing it.
    """

    inquiry = models.ForeignKey(
        "inquiries.Inquiry",
        on_delete=models.CASCADE,
        related_name="activities",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="crm_activities",
    )
    channel = models.CharField(max_length=20, choices=ActivityChannel.choices)
    body = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "crm_activities"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["inquiry", "created_at"], name="activity_inquiry_created_idx"),
        ]

    def __str__(self):
        return f"{self.channel} on {self.inquiry.inquiry_number}"
