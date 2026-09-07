from django.conf import settings
from django.db import models

from .base import TimeStampedModel


class NotificationChannel(models.TextChoices):
    EMAIL = "EMAIL", "Email"
    WHATSAPP = "WHATSAPP", "WhatsApp"


class NotificationStatus(models.TextChoices):
    SENT = "SENT", "Sent"
    FAILED = "FAILED", "Failed"


class NotificationLog(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notification_logs"
    )

    booking = models.ForeignKey(
        "bookings.Booking",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notification_logs"
    )

    inquiry = models.ForeignKey(
        "inquiries.Inquiry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notification_logs"
    )

    channel = models.CharField(
        max_length=20,
        choices=NotificationChannel.choices
    )

    event_type = models.CharField(max_length=100)

    recipient = models.CharField(max_length=255)

    subject = models.CharField(
        max_length=255,
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=NotificationStatus.choices
    )

    provider_message_id = models.CharField(
        max_length=255,
        blank=True
    )

    response_payload = models.JSONField(
        default=dict,
        blank=True
    )

    def __str__(self):
        return f"{self.channel} - {self.recipient} - {self.status}"