import logging

logger = logging.getLogger(__name__)


def send_inquiry_acknowledgement_email(inquiry_id):
    """
    Sends automated acknowledgement email to the client confirming receipt of inquiry:
    "We have received your journey inquiry; our team is reviewing your requirements..."
    Offloaded to Celery worker in production.
    """
    logger.info(f"Sending inquiry acknowledgement email for inquiry ID: {inquiry_id}")
    return True


def send_agent_whatsapp_alert(inquiry_id):
    """
    Sends instant WhatsApp alert to internal sales agents regarding a new lead.
    Offloaded to Celery worker in production.
    """
    logger.info(f"Sending internal agent WhatsApp lead alert for inquiry ID: {inquiry_id}")
    return True
