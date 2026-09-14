from datetime import timedelta
from decimal import Decimal
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.parse import urlsplit

import requests
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.b2b.models import B2BPartner, B2BAsset, B2BBooking, PartnerEmail
from apps.b2b.tasks import deliver_partner_email, dispatch_pending_partner_emails
from apps.bookings.models import Booking
from apps.common.testing import PortalFixtures


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class PartnerPortalTests(PortalFixtures, APITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        User = get_user_model()
        cls.partner_user = User.objects.create_user(email='agency@phase.test', password='StrongTestPass123!', role='B2B_PARTNER')
        cls.other_user = User.objects.create_user(email='other@phase.test', password='StrongTestPass123!', role='B2B_PARTNER')
        cls.partner = B2BPartner.objects.create(user=cls.partner_user, company_name='Agency', country='Italy', approved=True)
        cls.other = B2BPartner.objects.create(user=cls.other_user, company_name='Other', country='France', approved=True)
        cls.asset = B2BAsset.objects.create(title='Bronze PDF', trip=cls.trip,
            asset_type='WHITE_LABEL_ITINERARY', file='b2b_assets/test.pdf')
        cls.gold = B2BAsset.objects.create(title='Gold PDF', minimum_tier='GOLD',
            asset_type='WHITE_LABEL_ITINERARY', file='b2b_assets/gold.pdf')
        cls.ledger_ids = []
        for i, partner in enumerate([cls.partner, cls.other]):
            booking = Booking.objects.create(booking_reference=f'DS-PHASE-{i}', departure=cls.departure,
                customer_name='Traveler', customer_email=f'guest{i}@phase.test', num_travelers=1,
                total_amount_usd=1000, deposit_amount_usd=200, balance_amount_usd=800,
                trip_start_date=cls.departure.start_date)
            ledger = B2BBooking.objects.create(partner=partner, booking=booking, commission_rate=10,
                gross_amount_usd=1000, commission_amount_usd=100, net_amount_usd=900)
            cls.ledger_ids.append(ledger.pk)

    def registration(self, **extra):
        return dict(email='NEW@phase.test', password='StrongAgency123!', password_confirm='StrongAgency123!',
                    first_name='New', last_name='Partner', company_name='New Agency', country='Italy', **extra)

    def test_registration_and_after_commit_dispatch(self):
        with patch('apps.b2b.tasks.deliver_partner_email.delay') as delay:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post('/api/v1/b2b/register/', self.registration(), format='json')
            self.assertEqual(response.status_code, 201, response.data)
            delay.assert_called_once()
        user = get_user_model().objects.get(email='new@phase.test')
        self.assertEqual(user.role, 'B2B_PARTNER')
        self.assertFalse(user.b2b_profile.approved)
        self.assertEqual(PartnerEmail.objects.count(), 1)
        self.assertNotIn('password', response.json()['data'])

    def test_registration_validation_and_case_insensitive_duplicate(self):
        payload = self.registration()
        payload['password_confirm'] = 'different'
        self.assertEqual(self.client.post('/api/v1/b2b/register/', payload, format='json').status_code, 400)
        payload = self.registration()
        payload['email'] = 'AGENCY@phase.test'
        self.assertEqual(self.client.post('/api/v1/b2b/register/', payload, format='json').status_code, 400)
        self.assertEqual(PartnerEmail.objects.count(), 0)

    def test_registration_rollback_on_outbox_failure(self):
        before = get_user_model().objects.count()
        with patch('apps.b2b.serializers.partner_serializers.queue_partner_email', side_effect=RuntimeError):
            response = self.client.post('/api/v1/b2b/register/', self.registration(), format='json')
        self.assertEqual(response.status_code, 500)
        self.assertEqual(get_user_model().objects.count(), before)

    def test_pending_profile_access_but_no_assets_or_ledger(self):
        B2BPartner.objects.filter(pk=self.partner.pk).update(approved=False)
        self.partner_user.refresh_from_db()
        self.client.force_authenticate(self.partner_user)
        self.assertEqual(self.client.get('/api/v1/b2b/partners/me/').status_code, 200)
        for path in ['assets/', 'bookings/']:
            response = self.client.get('/api/v1/b2b/' + path)
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.data['error']['code'], 'PARTNER_UNAPPROVED')

    def test_profile_cannot_escalate_privileges(self):
        self.client.force_authenticate(self.partner_user)
        response = self.client.patch('/api/v1/b2b/partners/me/', {
            'company_name': 'Updated', 'agency_tier': 'PLATINUM', 'commission_rate': '99',
            'approved': False, 'phone': '+123456'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.partner.refresh_from_db()
        self.partner_user.refresh_from_db()
        self.assertEqual(self.partner.company_name, 'Updated')
        self.assertEqual(self.partner.agency_tier, 'BRONZE')
        self.assertTrue(self.partner.approved)
        self.assertEqual(self.partner_user.phone, '+123456')

    def test_approval_is_admin_only_and_queues_once(self):
        B2BPartner.objects.filter(pk=self.partner.pk).update(approved=False)
        path = f'/api/v1/b2b/partners/{self.partner.pk}/approve/'
        payload = {'approved': True, 'agency_tier': 'SILVER', 'commission_rate': '12.50'}
        self.client.force_authenticate(self.customer)
        self.assertEqual(self.client.post(path, payload).status_code, 403)
        self.client.force_authenticate(self.admin)
        with patch('apps.b2b.tasks.deliver_partner_email.delay') as delay:
            with self.captureOnCommitCallbacks(execute=True):
                self.assertEqual(self.client.post(path, payload).status_code, 200)
                self.assertEqual(self.client.post(path, payload).status_code, 200)
            delay.assert_called_once()
        self.partner.refresh_from_db()
        self.assertEqual(self.partner.commission_rate, Decimal('12.50'))
        payload['commission_rate'] = '101'
        self.assertEqual(self.client.post(path, payload).status_code, 400)

    def test_admin_partner_list_and_filters(self):
        self.client.force_authenticate(self.partner_user)
        self.assertEqual(self.client.get('/api/v1/b2b/partners/').status_code, 403)
        self.client.force_authenticate(self.admin)
        response = self.client.get('/api/v1/b2b/partners/?country=Italy&approved=true')
        self.assertEqual(response.data['count'], 1)

    def test_assets_filter_tiers_and_never_expose_file(self):
        self.client.force_authenticate(self.partner_user)
        response = self.client.get('/api/v1/b2b/assets/')
        self.assertEqual(response.data['count'], 1)
        self.assertNotIn('file', response.data['results'][0])
        self.assertIn('/download/', response.data['results'][0]['download_url'])
        response = self.client.get(f'/api/v1/b2b/assets/{self.gold.pk}/download/')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data['error']['code'], 'TIER_INSUFFICIENT')
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get('/api/v1/b2b/assets/').data['count'], 2)

    def test_private_file_token_checks_and_revocation(self):
        self.client.force_authenticate(self.partner_user)
        with TemporaryDirectory() as root, override_settings(B2B_PRIVATE_ROOT=root):
            self.asset.file.save('download.pdf', ContentFile(b'%PDF-test'))
            response = self.client.get(f'/api/v1/b2b/assets/{self.asset.pk}/download/')
            self.assertEqual(response.status_code, 200)
            link = urlsplit(response.data['download_url'])
            path = link.path + '?' + link.query
            download = self.client.get(path)
            self.assertEqual(download.status_code, 200)
            self.assertEqual(b''.join(download.streaming_content), b'%PDF-test')
            self.client.force_authenticate(self.other_user)
            self.assertEqual(self.client.get(path).status_code, 403)
            self.client.force_authenticate(self.partner_user)
            self.assertEqual(self.client.get(link.path + '?token=invalid').status_code, 403)
            with override_settings(B2B_DOWNLOAD_TTL=-1):
                self.assertEqual(self.client.get(path).status_code, 403)
            B2BAsset.objects.filter(pk=self.asset.pk).update(is_active=False)
            self.assertEqual(self.client.get(path).status_code, 404)

    def test_ledger_isolation_and_commission_timestamps(self):
        self.client.force_authenticate(self.partner_user)
        response = self.client.get('/api/v1/b2b/bookings/')
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(str(response.data['results'][0]['id']), str(self.ledger_ids[0]))
        path = f'/api/v1/b2b/bookings/{self.ledger_ids[1]}/commission/'
        self.assertEqual(self.client.patch(path, {'commission_status': 'PAID'}).status_code, 403)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get('/api/v1/b2b/bookings/').data['count'], 2)
        self.assertEqual(self.client.get('/api/v1/b2b/bookings/?from_date=invalid').status_code, 400)
        response = self.client.patch(path, {'commission_status': 'INVOICED'})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIsNotNone(response.data['commission_invoiced_at'])
        response = self.client.patch(path, {'commission_status': 'PAID'})
        timestamp = response.data['commission_paid_at']
        self.assertIsNotNone(timestamp)
        response = self.client.patch(path, {'commission_status': 'PAID'})
        self.assertEqual(response.data['commission_paid_at'], timestamp)

    def test_outbox_survives_broker_failure(self):
        with patch('apps.b2b.tasks.deliver_partner_email.delay', side_effect=OSError('broker unavailable')):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post('/api/v1/b2b/register/', self.registration(), format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(PartnerEmail.objects.filter(sent_at__isnull=True).count(), 1)

    @override_settings(RESEND_API_KEY='test-only-key')
    def test_worker_retry_and_duplicate_delivery(self):
        email = PartnerEmail.objects.create(recipient='test@phase.test', subject='Approved', body='Test')
        with patch('apps.b2b.tasks.requests.post', side_effect=requests.ConnectionError):
            deliver_partner_email(str(email.pk))
        email.refresh_from_db()
        self.assertIsNone(email.sent_at)
        self.assertEqual(email.attempts, 1)
        PartnerEmail.objects.filter(pk=email.pk).update(next_attempt_at=timezone.now() - timedelta(seconds=1))
        with patch('apps.b2b.tasks.requests.post') as post:
            deliver_partner_email(str(email.pk))
            deliver_partner_email(str(email.pk))
            post.assert_called_once()
            self.assertEqual(post.call_args.kwargs['headers']['Idempotency-Key'], f'partner-email/{email.pk}')
        email.refresh_from_db()
        self.assertIsNotNone(email.sent_at)

    def test_sweep_queues_only_due_unsent_messages(self):
        due = PartnerEmail.objects.create(recipient='due@phase.test', subject='Due', body='Test')
        PartnerEmail.objects.create(recipient='later@phase.test', subject='Later', body='Test',
                                    next_attempt_at=timezone.now() + timedelta(hours=1))
        PartnerEmail.objects.create(recipient='sent@phase.test', subject='Sent', body='Test', sent_at=timezone.now())
        with patch('apps.b2b.tasks.deliver_partner_email.delay') as delay:
            dispatch_pending_partner_emails()
            delay.assert_called_once_with(str(due.pk))
