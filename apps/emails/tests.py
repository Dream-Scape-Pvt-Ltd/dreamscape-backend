import base64
import hashlib
import hmac
import json
import time
from unittest.mock import MagicMock, patch

import requests
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase

from apps.emails.models import EmailKind, EmailStatus, EmailTemplate, OutboundEmail
from apps.emails.rendering import render, unknown_placeholders
from apps.emails.tasks import deliver_outbound_email, queue_email, queue_inquiry_acknowledgement

SECRET_BYTES = b"test-secret-bytes"
WEBHOOK_SECRET = "whsec_" + base64.b64encode(SECRET_BYTES).decode()


def make_email(**kwargs):
    defaults = dict(recipient="guest@example.com", subject="Hi", body_html="<p>Hi</p>", body_text="Hi")
    return OutboundEmail.objects.create(**{**defaults, **kwargs})


class RenderingTests(APITestCase):
    def test_html_values_are_escaped_and_unknown_values_blank(self):
        out = render("Hi {{full_name}} {{trip_title}}", {"full_name": "<b>Ann</b>"}, html=True)
        self.assertEqual(out, "Hi &lt;b&gt;Ann&lt;/b&gt; ")

    def test_unknown_placeholders_are_reported(self):
        self.assertEqual(unknown_placeholders("{{full_name}} {{secret}}"), ["secret"])


@override_settings(RESEND_API_KEY="re_test", DEFAULT_FROM_EMAIL="no-reply@example.com")
class DeliveryTests(APITestCase):
    @patch("apps.emails.tasks.requests.post")
    def test_success_marks_sent_and_stores_resend_id(self, post):
        post.return_value = MagicMock(status_code=200, json=lambda: {"id": "abc"})
        email = make_email(reply_to="team@example.com")
        deliver_outbound_email(str(email.pk))
        email.refresh_from_db()
        self.assertEqual((email.status, email.resend_id), (EmailStatus.SENT, "abc"))
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["reply_to"], "team@example.com")
        self.assertIn("html", payload)

    @patch("apps.emails.tasks.requests.post", side_effect=requests.ConnectionError)
    def test_network_failure_stays_queued_with_backoff(self, post):
        email = make_email()
        deliver_outbound_email(str(email.pk))
        email.refresh_from_db()
        self.assertEqual(email.status, EmailStatus.QUEUED)
        self.assertEqual(email.attempts, 1)
        self.assertIsNotNone(email.next_attempt_at)

    @patch("apps.emails.tasks.requests.post")
    def test_client_error_fails_permanently(self, post):
        response = MagicMock(status_code=422)
        response.raise_for_status.side_effect = requests.HTTPError("422")
        post.return_value = response
        email = make_email()
        deliver_outbound_email(str(email.pk))
        email.refresh_from_db()
        self.assertEqual(email.status, EmailStatus.FAILED)


@override_settings(INQUIRY_NOTIFY_EMAIL="team@example.com")
class AcknowledgementTests(APITestCase):
    def test_inquiry_post_queues_acknowledgement(self):
        with self.captureOnCommitCallbacks(execute=False):
            response = self.client.post(
                "/api/v1/inquiries/",
                {"inquiry_type": "GENERAL", "full_name": "Ann Guest", "email": "ann@example.com",
                 "message": "Hello there"},
                format="json",
            )
        self.assertEqual(response.status_code, 201, response.content)
        email = OutboundEmail.objects.get(recipient="ann@example.com")
        self.assertEqual(email.kind, EmailKind.AUTO_ACK)
        self.assertEqual(email.reply_to, "team@example.com")
        self.assertIn("Ann Guest", email.body_text)

    def test_bounced_address_is_not_emailed_again(self):
        make_email(recipient="bad@example.com", status=EmailStatus.BOUNCED)
        inquiry = MagicMock(email="bad@example.com")
        self.assertIsNone(queue_inquiry_acknowledgement(inquiry))

    def test_failure_to_queue_never_raises(self):
        with patch("apps.emails.tasks.queue_email", side_effect=RuntimeError("boom")):
            inquiry = MagicMock(email="x@example.com")
            self.assertIsNone(queue_inquiry_acknowledgement(inquiry))


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class AdminApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.admin = User.objects.create_user(email="admin@t.test", password="StrongTestPass123!", role="ADMIN")
        cls.agent = User.objects.create_user(email="agent@t.test", password="StrongTestPass123!", role="SALES_AGENT")
        cls.customer = User.objects.create_user(email="cust@t.test", password="StrongTestPass123!", role="CUSTOMER")

    def test_customers_and_anonymous_are_blocked(self):
        self.assertIn(self.client.get("/api/v1/emails/").status_code, (401, 403))
        self.client.force_authenticate(self.customer)
        self.assertEqual(self.client.get("/api/v1/emails/").status_code, 403)

    def test_seeded_templates_exist_and_system_one_cannot_be_deleted(self):
        template = EmailTemplate.objects.get(slug="inquiry-received")
        self.assertTrue(template.is_system)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.delete(f"/api/v1/emails/templates/{template.pk}/").status_code, 400)

    def test_agent_can_send_but_not_edit_templates(self):
        self.client.force_authenticate(self.agent)
        template = EmailTemplate.objects.get(slug="follow-up")
        self.assertEqual(
            self.client.patch(f"/api/v1/emails/templates/{template.pk}/", {"name": "x"}, format="json").status_code, 403
        )
        with self.captureOnCommitCallbacks(execute=False):
            response = self.client.post(
                "/api/v1/emails/",
                {"recipient": "guest@example.com", "template": str(template.pk)},
                format="json",
            )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertTrue(OutboundEmail.objects.filter(kind=EmailKind.TEMPLATE, sent_by=self.agent).exists())

    def test_unknown_placeholder_rejected_on_template_save(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            "/api/v1/emails/templates/",
            {"slug": "bad", "name": "Bad", "subject": "{{nope}}", "body_html": "x", "body_text": "x"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_cannot_send_to_bounced_address(self):
        make_email(recipient="bad@example.com", status=EmailStatus.COMPLAINED)
        self.client.force_authenticate(self.agent)
        response = self.client.post(
            "/api/v1/emails/",
            {"recipient": "bad@example.com", "subject": "Hi", "body_text": "Hello"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_only_failed_emails_can_be_resent(self):
        self.client.force_authenticate(self.agent)
        sent = make_email(status=EmailStatus.SENT)
        self.assertEqual(self.client.post(f"/api/v1/emails/{sent.pk}/resend/").status_code, 400)
        failed = make_email(status=EmailStatus.FAILED, attempts=8)
        with self.captureOnCommitCallbacks(execute=False):
            self.assertEqual(self.client.post(f"/api/v1/emails/{failed.pk}/resend/").status_code, 200)
        failed.refresh_from_db()
        self.assertEqual((failed.status, failed.attempts), (EmailStatus.QUEUED, 0))


@override_settings(RESEND_WEBHOOK_SECRET=WEBHOOK_SECRET)
class WebhookTests(APITestCase):
    def post_event(self, event_type, email_id="re_1", sign=True):
        body = json.dumps({"type": event_type, "created_at": "2026-10-16T10:00:00Z", "data": {"email_id": email_id}})
        ts = str(int(time.time()))
        signed = f"msg_1.{ts}.{body}".encode()
        sig = base64.b64encode(hmac.new(SECRET_BYTES, signed, hashlib.sha256).digest()).decode()
        headers = {"HTTP_SVIX_ID": "msg_1", "HTTP_SVIX_TIMESTAMP": ts,
                   "HTTP_SVIX_SIGNATURE": f"v1,{sig}" if sign else "v1,bogus"}
        return self.client.post("/api/v1/emails/webhook/resend/", body, content_type="application/json", **headers)

    def test_bad_signature_rejected(self):
        email = make_email(status=EmailStatus.SENT, resend_id="re_1")
        self.assertEqual(self.post_event("email.delivered", sign=False).status_code, 400)
        email.refresh_from_db()
        self.assertEqual(email.status, EmailStatus.SENT)

    def test_delivered_then_late_sent_event_does_not_downgrade(self):
        email = make_email(status=EmailStatus.SENT, resend_id="re_1")
        self.assertEqual(self.post_event("email.delivered").status_code, 200)
        self.post_event("email.sent")
        email.refresh_from_db()
        self.assertEqual(email.status, EmailStatus.DELIVERED)
        self.assertIsNotNone(email.last_event_at)

    def test_bounce_is_recorded(self):
        email = make_email(status=EmailStatus.SENT, resend_id="re_1")
        self.post_event("email.bounced")
        email.refresh_from_db()
        self.assertEqual(email.status, EmailStatus.BOUNCED)

    def test_unknown_email_id_is_ignored(self):
        self.assertEqual(self.post_event("email.delivered", email_id="nope").status_code, 200)
