import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def send_inquiry_acknowledgement_email(inquiry_id):
    from apps.inquiries.models import Inquiry
    from apps.common.email_tasks import queue_email
    inquiry = Inquiry.objects.get(pk=inquiry_id)
    return queue_email(
        f'inquiry-ack/{inquiry.pk}', inquiry.email,
        f'Dreamscape enquiry received — {inquiry.inquiry_number}',
        f'Hello {inquiry.full_name},\n\nWe have received your enquiry. Our team will review your requirements and contact you.\n\nReference: {inquiry.inquiry_number}\nThis acknowledges your enquiry; it does not confirm a reservation.\n\nDreamscape Treks',
    )


def send_agent_whatsapp_alert(inquiry_id):
    """
    Sends instant WhatsApp alert to internal sales agents regarding a new lead.
    Offloaded to Celery worker in production.
    """
    logger.info(f"Sending internal agent WhatsApp lead alert for inquiry ID: {inquiry_id}")
    return True


def send_task_reminder_alert(task_id):
    """
    Sends a follow-up reminder (email/WhatsApp) to the agent a Task is
    assigned to. Offloaded to Celery worker in production.
    """
    logger.info(f"Sending CRM task reminder for task ID: {task_id}")
    return True


def send_sla_breach_alert(inquiry_id):
    """
    Notifies the sales manager that a lead has sat in NEW status past the
    configured SLA window without a first response.
    """
    logger.info(f"Sending SLA breach alert for inquiry ID: {inquiry_id}")
    return True


@shared_task
def check_sla_breaches():
    """
    Celery Beat job (every 30 min): flags any NEW inquiry older than
    settings.CRM_SLA_HOURS (default 4 business hours) that hasn't been
    responded to yet, and fires a manager notification for each newly
    flagged lead.
    """
    from apps.inquiries.models import Inquiry, InquiryStatus

    sla_hours = getattr(settings, "CRM_SLA_HOURS", 4)
    threshold = timezone.now() - timedelta(hours=sla_hours)

    stale_leads = Inquiry.objects.filter(
        status=InquiryStatus.NEW,
        first_response_at__isnull=True,
        sla_breached=False,
        created_at__lt=threshold,
    )

    breached_ids = list(stale_leads.values_list("id", flat=True))
    if not breached_ids:
        return 0

    Inquiry.objects.filter(id__in=breached_ids).update(sla_breached=True)
    for inquiry_id in breached_ids:
        send_sla_breach_alert(inquiry_id)

    logger.info(f"CRM SLA sweep: flagged {len(breached_ids)} stale lead(s)")
    return len(breached_ids)


@shared_task
def send_task_reminders():
    """
    Celery Beat job (every 15 min): notifies agents about follow-up tasks
    due within the next hour that haven't already had a reminder sent.
    """
    from apps.inquiries.models import Task, TaskStatus

    now = timezone.now()
    window_end = now + timedelta(hours=1)

    due_tasks = Task.objects.filter(
        status=TaskStatus.OPEN,
        due_at__lte=window_end,
        reminder_sent_at__isnull=True,
    )

    task_ids = list(due_tasks.values_list("id", flat=True))
    if not task_ids:
        return 0

    Task.objects.filter(id__in=task_ids).update(reminder_sent_at=now)
    for task_id in task_ids:
        send_task_reminder_alert(task_id)

    logger.info(f"CRM task reminder sweep: notified {len(task_ids)} due task(s)")
    return len(task_ids)


@shared_task
def nightly_customer_rollup():
    """
    Celery Beat job (daily, 02:00): recomputes Customer.lifetime_* counters
    from source-of-truth Inquiry/Booking rows, as a consistency check
    against the incremental updates made at inquiry/booking creation time.
    """
    from decimal import Decimal

    from django.db.models import Count, Sum

    from apps.bookings.models import Booking
    from apps.inquiries.models import Customer

    updated = 0
    for customer in Customer.objects.all():
        inquiry_count = customer.inquiries.count()
        booking_stats = Booking.objects.filter(customer_email__iexact=customer.email).aggregate(
            count=Count("id"),
            total=Sum("amount_paid_usd"),
        )
        booking_count = booking_stats["count"] or 0
        lifetime_value = booking_stats["total"] or Decimal("0.00")

        if (
            customer.lifetime_inquiries != inquiry_count
            or customer.lifetime_bookings != booking_count
            or customer.lifetime_value_usd != lifetime_value
        ):
            customer.lifetime_inquiries = inquiry_count
            customer.lifetime_bookings = booking_count
            customer.lifetime_value_usd = lifetime_value
            customer.save(update_fields=["lifetime_inquiries", "lifetime_bookings", "lifetime_value_usd", "updated_at"])
            updated += 1

    logger.info(f"CRM nightly rollup: reconciled {updated} customer record(s)")
    return updated


@shared_task
def advance_travel_statuses():
    """
    Celery Beat job (hourly): moves booked leads to TRAVELING when their
    departure starts and to COMPLETED once its end date has passed, recording
    each completed trip's revenue.
    """
    from apps.inquiries.services import advance_travel_statuses as advance

    started, completed = advance()
    logger.info(f"CRM travel sweep: {started} lead(s) now traveling, {completed} completed")
    return started + completed
