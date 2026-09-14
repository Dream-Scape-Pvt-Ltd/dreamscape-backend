import logging
from datetime import timedelta

import requests
from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.b2b.models import PartnerEmail

logger = logging.getLogger(__name__)


def queue_partner_email(recipient, subject, body):
    email = PartnerEmail.objects.create(recipient=recipient, subject=subject, body=body)
    # The outbox sweep retries publishing if Redis is unavailable after commit.
    def publish():
        deliver_partner_email.delay(str(email.pk))
    transaction.on_commit(publish, robust=True)


@shared_task
def deliver_partner_email(email_id):
    with transaction.atomic():
        email = PartnerEmail.objects.select_for_update().get(pk=email_id)
        now = timezone.now()
        if email.sent_at or (email.next_attempt_at and email.next_attempt_at > now):
            return
        try:
            if not settings.RESEND_API_KEY:
                raise ValueError("RESEND_API_KEY is not configured")
            response = requests.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}",
                         "Idempotency-Key": f"partner-email/{email.pk}"},
                json={"from": settings.DEFAULT_FROM_EMAIL, "to": [email.recipient],
                      "subject": email.subject, "text": email.body},
                timeout=15,
            )
            response.raise_for_status()
        except (requests.RequestException, ValueError):
            # Avoid logging provider payloads or recipient data.
            logger.warning("Partner email %s delivery failed; retained for retry", email.pk)
            email.attempts += 1
            email.next_attempt_at = now + timedelta(seconds=min(3600, 30 * 2 ** min(email.attempts, 7)))
            email.save(update_fields=["attempts", "next_attempt_at", "updated_at"])
            return
        email.sent_at = now
        email.save(update_fields=["sent_at", "updated_at"])


@shared_task
def dispatch_pending_partner_emails():
    ids = PartnerEmail.objects.filter(sent_at__isnull=True).filter(
        Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=timezone.now())
    ).order_by("created_at").values_list("pk", flat=True)[:100]
    for email_id in ids:
        deliver_partner_email.delay(str(email_id))
