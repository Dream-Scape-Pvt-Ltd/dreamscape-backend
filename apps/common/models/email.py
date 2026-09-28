from django.db import models
from .base import TimeStampedModel

class TransactionalEmail(TimeStampedModel):
    event_key = models.CharField(max_length=200, unique=True)
    recipient = models.EmailField()
    subject = models.CharField(max_length=255)
    body = models.TextField()
    sent_at = models.DateTimeField(null=True, blank=True, db_index=True)
    first_attempt_at = models.DateTimeField(null=True, blank=True)
    next_attempt_at = models.DateTimeField(null=True, blank=True, db_index=True)
    attempts = models.PositiveIntegerField(default=0)
    needs_review = models.BooleanField(default=False)
    provider_message_id = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = 'transactional_email_outbox'
