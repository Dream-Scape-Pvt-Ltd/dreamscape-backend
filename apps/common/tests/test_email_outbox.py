from datetime import timedelta
from unittest.mock import patch, Mock
from django.test import TestCase, override_settings
from django.utils import timezone
from apps.common.models import TransactionalEmail
from apps.common.email_tasks import queue_email, deliver_email

@override_settings(RESEND_API_KEY='test-key',DEFAULT_FROM_EMAIL='team@example.test')
class EmailOutboxTests(TestCase):
    def test_commit_queues_once_without_external_io_and_preserves_on_broker_failure(self):
        with patch('apps.common.email_tasks.deliver_email.delay') as publish:
            with self.captureOnCommitCallbacks(execute=True):
                email=queue_email('ack/one','guest@example.test','Received','Your reference')
                queue_email('ack/one','guest@example.test','Received','Your reference')
            self.assertEqual(TransactionalEmail.objects.count(),1)
            publish.assert_called_once_with(str(email.pk))

    def test_delivery_is_idempotent_and_uses_provider_key(self):
        email=TransactionalEmail.objects.create(event_key='ack/two',recipient='guest@example.test',subject='Received',body='Reference')
        response=Mock();response.json.return_value={'id':'provider-one'}
        with patch('apps.common.email_tasks.requests.post',return_value=response) as send:
            deliver_email(str(email.pk));deliver_email(str(email.pk))
            send.assert_called_once()
            self.assertEqual(send.call_args.kwargs['headers']['Idempotency-Key'],f'transactional/{email.pk}')
        email.refresh_from_db();self.assertIsNotNone(email.sent_at)

    @override_settings(RESEND_API_KEY='')
    def test_missing_config_is_retained_not_falsely_sent(self):
        email=TransactionalEmail.objects.create(event_key='ack/three',recipient='guest@example.test',subject='Received',body='Reference')
        with patch('apps.common.email_tasks.requests.post') as send:deliver_email(str(email.pk));send.assert_not_called()
        email.refresh_from_db();self.assertIsNone(email.sent_at);self.assertEqual(email.attempts,1)

    def test_expired_ambiguous_attempt_requires_review(self):
        email=TransactionalEmail.objects.create(event_key='ack/four',recipient='guest@example.test',subject='Received',body='Reference',first_attempt_at=timezone.now()-timedelta(hours=24))
        with patch('apps.common.email_tasks.requests.post') as send:deliver_email(str(email.pk));send.assert_not_called()
        email.refresh_from_db();self.assertTrue(email.needs_review)
