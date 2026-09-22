import logging

from celery import shared_task

logger = logging.getLogger(__name__)


def send_booking_confirmation_email(booking_id):
    """
    Transactional email trigger for booking confirmation.
    Offloaded to asynchronous worker when Celery is enabled.
    """
    logger.info(f"Triggering booking confirmation email for booking ID: {booking_id}")
    return True


@shared_task
def send_waitlist_offer_email(entry_id):
    """
    Tell a waitlisted traveller a seat has opened up, with the deadline to claim it.

    Dispatched via transaction.on_commit from promote_waitlist, so this never
    fires for a promotion that was rolled back.
    """
    from apps.bookings.models import DepartureWaitlistEntry

    entry = DepartureWaitlistEntry.objects.filter(id=entry_id).first()
    if not entry:
        logger.warning("Waitlist offer email skipped: entry %s no longer exists", entry_id)
        return False

    logger.info(
        "Sending waitlist seat offer to %s for departure %s (expires %s)",
        entry.customer_email,
        entry.departure_id,
        entry.offer_expires_at,
    )
    return True


@shared_task
def expire_waitlist_offers():
    """
    Lapse unclaimed waitlist offers and serve the next traveller in each queue.
    Scheduled via Celery Beat.
    """
    from apps.bookings.services import expire_stale_offers

    expired = expire_stale_offers()
    logger.info("Expired %s stale waitlist offer(s)", expired)
    return expired
