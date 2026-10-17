import logging
from datetime import timedelta

import requests
from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import EmailKind, EmailStatus, OutboundEmail
from .rendering import inquiry_context, render

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 8
AUTO_ACK_SLUG = "inquiry-received"


def is_suppressed(address):
    """True once an address has bounced or reported us as spam; sending again hurts sender reputation."""
    return OutboundEmail.objects.filter(
        recipient__iexact=address, status__in=[EmailStatus.BOUNCED, EmailStatus.COMPLAINED]
    ).exists()


def queue_email(*, recipient, subject, body_html, body_text, kind=EmailKind.MANUAL, reply_to="",
                template=None, inquiry=None, sent_by=None):
    email = OutboundEmail.objects.create(
        recipient=recipient, subject=subject, body_html=body_html, body_text=body_text, kind=kind,
        reply_to=reply_to, template=template, inquiry=inquiry, sent_by=sent_by,
    )
    # The outbox sweep retries publishing if Redis is unavailable after commit.
    transaction.on_commit(lambda: deliver_outbound_email.delay(str(email.pk)), robust=True)
    return email


def queue_inquiry_acknowledgement(inquiry):
    """Sends the customer the 'we received your inquiry' no-reply email. Never raises."""
    from .models import EmailTemplate

    try:
        template = EmailTemplate.objects.filter(slug=AUTO_ACK_SLUG, is_active=True).first()
        if not template or not inquiry.email or is_suppressed(inquiry.email):
            return None
        context = inquiry_context(inquiry)
        # Savepoint: a failure here must not poison the caller's transaction.
        with transaction.atomic():
            return queue_email(
                recipient=inquiry.email,
                subject=render(template.subject, context, html=False),
                body_html=render(template.body_html, context, html=True),
                body_text=render(template.body_text, context, html=False),
                kind=EmailKind.AUTO_ACK,
                # From is no-reply, so replies go to the sales inbox.
                reply_to=settings.INQUIRY_NOTIFY_EMAIL or "",
                template=template,
                inquiry=inquiry,
            )
    except Exception:
        logger.exception("Could not queue acknowledgement for inquiry %s", inquiry.pk)
        return None


@shared_task
def deliver_outbound_email(email_id):
    with transaction.atomic():
        email = OutboundEmail.objects.select_for_update().get(pk=email_id)
        now = timezone.now()
        if email.status != EmailStatus.QUEUED or (email.next_attempt_at and email.next_attempt_at > now):
            return
        permanent = False
        try:
            if not settings.RESEND_API_KEY:
                raise ValueError("RESEND_API_KEY is not configured")
            payload = {"from": settings.DEFAULT_FROM_EMAIL, "to": [email.recipient], "subject": email.subject,
                       "html": email.body_html, "text": email.body_text}
            if email.reply_to:
                payload["reply_to"] = email.reply_to
            response = requests.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}",
                         "Idempotency-Key": f"outbound-email/{email.pk}"},
                json=payload,
                timeout=15,
            )
            # 4xx (other than rate limiting) will not succeed on retry.
            permanent = 400 <= response.status_code < 500 and response.status_code != 429
            response.raise_for_status()
            resend_id = (response.json() or {}).get("id", "")
        except (requests.RequestException, ValueError) as exc:
            # Avoid logging provider payloads or recipient data.
            logger.warning("Email %s delivery failed; retained for retry", email.pk)
            email.attempts += 1
            email.last_error = str(exc)[:255] if isinstance(exc, ValueError) else f"{type(exc).__name__}"
            if permanent or email.attempts >= MAX_ATTEMPTS:
                email.status = EmailStatus.FAILED
                email.next_attempt_at = None
            else:
                email.next_attempt_at = now + timedelta(seconds=min(3600, 30 * 2 ** min(email.attempts, 7)))
            email.save(update_fields=["attempts", "last_error", "status", "next_attempt_at", "updated_at"])
            return
        email.status = EmailStatus.SENT
        email.sent_at = now
        email.resend_id = resend_id
        email.last_error = ""
        email.next_attempt_at = None
        email.save(update_fields=["status", "sent_at", "resend_id", "last_error", "next_attempt_at", "updated_at"])


@shared_task
def dispatch_pending_outbound_emails():
    ids = OutboundEmail.objects.filter(status=EmailStatus.QUEUED).filter(
        Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=timezone.now())
    ).order_by("created_at").values_list("pk", flat=True)[:100]
    for email_id in ids:
        deliver_outbound_email.delay(str(email_id))
