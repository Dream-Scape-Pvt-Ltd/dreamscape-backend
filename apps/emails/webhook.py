import base64
import hashlib
import hmac
import time

from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.exceptions import _build_error_envelope

from .models import EmailStatus, OutboundEmail

TOLERANCE_SECONDS = 300

# Higher rank wins, so a late "sent" event can never overwrite "delivered".
RANK = {EmailStatus.QUEUED: 0, EmailStatus.FAILED: 0, EmailStatus.SENT: 1,
        EmailStatus.DELIVERED: 2, EmailStatus.BOUNCED: 3, EmailStatus.COMPLAINED: 4}
EVENT_STATUS = {
    "email.sent": EmailStatus.SENT,
    "email.delivered": EmailStatus.DELIVERED,
    "email.bounced": EmailStatus.BOUNCED,
    "email.complained": EmailStatus.COMPLAINED,
}


def verify_signature(secret, headers, body):
    """Svix signature check (Resend signs webhooks with Svix)."""
    msg_id = headers.get("svix-id", "")
    timestamp = headers.get("svix-timestamp", "")
    signatures = headers.get("svix-signature", "")
    if not (secret and msg_id and timestamp and signatures):
        return False
    try:
        if abs(time.time() - int(timestamp)) > TOLERANCE_SECONDS:
            return False
        key = base64.b64decode(secret.removeprefix("whsec_"))
    except (ValueError, TypeError):
        return False
    signed = f"{msg_id}.{timestamp}.".encode() + body
    expected = base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode()
    return any(hmac.compare_digest(expected, part.split(",", 1)[-1]) for part in signatures.split())


class ResendWebhookView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = []

    def post(self, request):
        if not verify_signature(settings.RESEND_WEBHOOK_SECRET, request.headers, request.body):
            return Response(_build_error_envelope("INVALID_SIGNATURE", "Invalid signature.", None), status=400)
        event = request.data if isinstance(request.data, dict) else {}
        status = EVENT_STATUS.get(event.get("type"))
        data = event.get("data") or {}
        email_id = data.get("email_id")
        if status and email_id:
            email = OutboundEmail.objects.filter(resend_id=email_id).first()
            if email:
                email.last_event_at = parse_datetime(event.get("created_at") or "") or timezone.now()
                fields = ["last_event_at", "updated_at"]
                if RANK[status] > RANK[email.status]:
                    email.status = status
                    fields.append("status")
                email.save(update_fields=fields)
        return Response({"received": True})
