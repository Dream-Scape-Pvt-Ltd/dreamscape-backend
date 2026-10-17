from django.conf import settings
from django.db import models

from apps.common.models.base import TimeStampedModel


class EmailTemplate(TimeStampedModel):
    """Editable email body with {{variable}} placeholders (see rendering.VARIABLES)."""

    slug = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=120)
    subject = models.CharField(max_length=200)
    body_html = models.TextField()
    body_text = models.TextField()
    is_system = models.BooleanField(
        default=False, help_text="Used automatically by the system; can be edited but not deleted."
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "email_templates"
        ordering = ["name"]

    def __str__(self):
        return self.name


class EmailKind(models.TextChoices):
    AUTO_ACK = "AUTO_ACK", "Automatic acknowledgement"
    TEMPLATE = "TEMPLATE", "From template"
    MANUAL = "MANUAL", "Written by hand"


class EmailStatus(models.TextChoices):
    QUEUED = "QUEUED", "Queued"
    SENT = "SENT", "Sent"
    DELIVERED = "DELIVERED", "Delivered"
    BOUNCED = "BOUNCED", "Bounced"
    COMPLAINED = "COMPLAINED", "Marked as spam"
    FAILED = "FAILED", "Failed"


class OutboundEmail(TimeStampedModel):
    """Sent-mail log that doubles as the delivery outbox (rows stay QUEUED until Resend accepts them)."""

    recipient = models.EmailField(db_index=True)
    subject = models.CharField(max_length=200)
    body_html = models.TextField()
    body_text = models.TextField()
    reply_to = models.EmailField(blank=True)
    kind = models.CharField(max_length=20, choices=EmailKind.choices, default=EmailKind.MANUAL)
    template = models.ForeignKey(EmailTemplate, null=True, blank=True, on_delete=models.SET_NULL, related_name="emails")
    inquiry = models.ForeignKey(
        "inquiries.Inquiry", null=True, blank=True, on_delete=models.SET_NULL, related_name="emails"
    )
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    status = models.CharField(max_length=12, choices=EmailStatus.choices, default=EmailStatus.QUEUED, db_index=True)
    resend_id = models.CharField(max_length=64, blank=True, db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=255, blank=True)
    last_event_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "outbound_emails"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.subject} -> {self.recipient} ({self.status})"
