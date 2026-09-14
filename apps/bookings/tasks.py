import logging

logger = logging.getLogger(__name__)


def send_booking_confirmation_email(booking_id):
    """
    Transactional email trigger for booking confirmation.
    Offloaded to asynchronous worker when Celery is enabled.
    """
    logger.info(f"Triggering booking confirmation email for booking ID: {booking_id}")
    return True
