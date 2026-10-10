import logging

import requests
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)


class ResendEmailBackend(BaseEmailBackend):
    """Sends Django mail (plain-text body) through the Resend HTTP API."""

    def send_messages(self, email_messages):
        sent = 0
        for message in email_messages:
            try:
                response = requests.post(
                    "https://api.resend.com/emails",
                    headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
                    json={"from": message.from_email or settings.DEFAULT_FROM_EMAIL,
                          "to": list(message.to), "subject": message.subject,
                          "text": message.body},
                    timeout=15,
                )
                response.raise_for_status()
            except requests.RequestException:
                # Avoid logging provider payloads or recipient data.
                logger.exception("Resend delivery failed for %r", message.subject)
                if not self.fail_silently:
                    raise
                continue
            sent += 1
        return sent
