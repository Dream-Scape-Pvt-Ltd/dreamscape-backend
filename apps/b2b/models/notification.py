from django.db import models
from apps.common.models.base import TimeStampedModel


class PartnerEmail(TimeStampedModel):
    """Durable email outbox; broker outages do not discard onboarding emails."""

    recipient = models.EmailField()
    subject = models.CharField(max_length=255)
    body = models.TextField()
    sent_at = models.DateTimeField(null=True, blank=True, db_index=True)
    next_attempt_at = models.DateTimeField(null=True, blank=True, db_index=True)
    attempts = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "b2b_partner_emails"
