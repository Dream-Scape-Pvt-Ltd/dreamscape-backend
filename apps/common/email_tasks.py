import logging
from datetime import timedelta
import requests
from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from apps.common.models import TransactionalEmail

logger = logging.getLogger(__name__)

def queue_email(event_key, recipient, subject, body):
    email, created = TransactionalEmail.objects.get_or_create(event_key=event_key, defaults={'recipient':recipient,'subject':subject,'body':body})
    if created:
        transaction.on_commit(lambda: deliver_email.delay(str(email.pk)), robust=True)
    return email

@shared_task
def deliver_email(email_id):
    with transaction.atomic():
        email = TransactionalEmail.objects.select_for_update().get(pk=email_id)
        now = timezone.now()
        if email.sent_at or email.needs_review or (email.next_attempt_at and email.next_attempt_at > now):
            return
        # Do not automatically retry beyond the provider's idempotency window.
        if email.first_attempt_at and now-email.first_attempt_at > timedelta(hours=23):
            email.needs_review = True
            email.save(update_fields=['needs_review','updated_at'])
            return
        try:
            if not settings.RESEND_API_KEY:
                raise ValueError('Email provider is not configured')
            if not email.first_attempt_at:
                email.first_attempt_at = now
                email.save(update_fields=['first_attempt_at','updated_at'])
            response = requests.post('https://api.resend.com/emails',
                headers={'Authorization':f'Bearer {settings.RESEND_API_KEY}','Idempotency-Key':f'transactional/{email.pk}'},
                json={'from':settings.DEFAULT_FROM_EMAIL,'to':[email.recipient],'subject':email.subject,'text':email.body},timeout=15)
            response.raise_for_status()
            provider_id = response.json().get('id')
            if not provider_id:
                raise ValueError('Provider did not confirm acceptance')
        except (requests.RequestException, ValueError):
            email.attempts += 1
            email.next_attempt_at = now + timedelta(seconds=min(3600,30 * 2 ** min(email.attempts,7)))
            email.save(update_fields=['attempts','next_attempt_at','updated_at'])
            logger.warning('Transactional email %s retained for retry',email.pk)
            return
        email.sent_at = now
        email.provider_message_id = provider_id
        email.save(update_fields=['sent_at','provider_message_id','updated_at'])

@shared_task
def dispatch_pending_emails():
    ids = TransactionalEmail.objects.filter(sent_at__isnull=True,needs_review=False).filter(Q(next_attempt_at__isnull=True)|Q(next_attempt_at__lte=timezone.now())).order_by('created_at').values_list('pk',flat=True)[:100]
    for email_id in ids:
        deliver_email.delay(str(email_id))
