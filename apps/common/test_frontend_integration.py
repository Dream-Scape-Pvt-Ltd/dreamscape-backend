"""Opt-in real HTTP integration: FRONTEND_DIR points to an already built Next checkout."""
import os
import shutil
import subprocess
import time
from datetime import date, timedelta
from pathlib import Path
from unittest import skipUnless

import requests
from django.contrib.auth import get_user_model
from django.test import LiveServerTestCase, override_settings
from apps.accounts.models import UserRole
from apps.destinations.models import Destination, ActivityCategory
from apps.trips.models import Trip, TripDeparture


@skipUnless(os.environ.get('FRONTEND_DIR'), 'Set FRONTEND_DIR to run the real Next/Django integration.')
@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class FrontendIntegrationTests(LiveServerTestCase):
    def test_guest_booking_and_admin_cms_over_http(self):
        destination = Destination.objects.create(name='Integration Nepal', slug='integration-nepal', country='NEPAL')
        category = ActivityCategory.objects.create(name='Treks', slug='treks')
        trip = Trip.objects.create(title='Integration Trek', slug='integration-trek', destination=destination,
            category=category, duration_days=7, difficulty_grade='GRADE_2', starting_price_usd=1000, overview='Test trail')
        departure = TripDeparture.objects.create(trip=trip, start_date=date.today()+timedelta(days=60),
            end_date=date.today()+timedelta(days=67), price_usd=1000, max_seats=4, available_seats=4)
        get_user_model().objects.create_user(email='integration@example.test', password='IntegrationOnly123!', role=UserRole.ADMIN, is_staff=True)
        root = Path(os.environ['FRONTEND_DIR']).resolve()
        env = {**os.environ, 'BACKEND_API_URL': self.live_server_url+'/api/v1', 'PORT': '3101'}
        process = subprocess.Popen([shutil.which('node'), str(root/'node_modules/next/dist/bin/next'), 'start', '--hostname', '127.0.0.1', '--port', '3101'],
            cwd=root, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        base = 'http://127.0.0.1:3101'
        try:
            for _ in range(100):
                try:
                    requests.get(base+'/api/auth/me', timeout=1)
                    break
                except requests.RequestException:
                    if process.poll() is not None: self.fail('Next integration server did not start.')
                    time.sleep(.1)
            guest = requests.Session()
            catalog = guest.get(base+'/api/trips', timeout=15)
            self.assertEqual(catalog.status_code, 200, catalog.text)
            self.assertIn('integration-trek', catalog.text)
            passenger = dict(full_name='Test Traveller', date_of_birth='1990-01-01', nationality='Nepal',
                passport_number='TEST123', passport_expiry_date=str(date.today()+timedelta(days=800)),
                insurance_provider='Test', insurance_policy_number='TEST', insurance_emergency_phone='123456789',
                emergency_contact_name='Test Contact', emergency_contact_phone='123456789')
            saved = guest.post(base+'/api/bookings', json=dict(trek_slug=trip.slug, departure_id=str(departure.id),
                customer_name='Test Traveller', customer_email='traveller@example.test', payment_type='DEPOSIT_20', passengers=[passenger]), timeout=15)
            self.assertEqual(saved.status_code, 201, saved.text)
            reference = saved.json()['receipt']['booking_reference']
            self.assertNotIn('access_token', saved.text)
            self.assertNotIn('passport_number', saved.text)
            self.assertTrue(any(c.name.startswith('dreamscape_booking_') and c.has_nonstandard_attr('HttpOnly') for c in guest.cookies))
            self.assertEqual(guest.get(base+'/api/bookings/'+reference, timeout=15).status_code, 200)
            self.assertEqual(requests.get(base+'/api/bookings/'+reference, timeout=15).status_code, 401)
            account = guest.get(base+'/api/account', timeout=15).json()
            self.assertEqual(account['bookings'][0]['booking_reference'], reference)
            departure.refresh_from_db()
            self.assertEqual(departure.available_seats, 3)
            inquiry = guest.post(base+'/api/inquiries', json={'full_name':'Integration Guest',
                'email':'inquiry@example.test', 'message':'Please help plan a test journey.',
                'trip':str(trip.id), 'group_size':2}, timeout=15)
            self.assertEqual(inquiry.status_code, 201, inquiry.text)
            from apps.inquiries.models import Inquiry
            self.assertTrue(Inquiry.objects.filter(inquiry_number=inquiry.json()['reference'], trip=trip).exists())
            review = guest.post(base+'/api/reviews', json={'trek':trip.slug, 'reviewer_name':'Integration Guest',
                'reviewer_country':'Nepal', 'title':'Test review', 'content':'Test review for moderation.',
                'rating_overall':5}, timeout=15)
            self.assertEqual(review.status_code, 201, review.text)
            public_reviews = guest.get(base+'/api/reviews?trek='+trip.slug, timeout=15)
            self.assertEqual(public_reviews.json()['reviews'], [])
            admin = requests.Session()
            signed = admin.post(base+'/api/auth/login', json={'email':'integration@example.test','password':'IntegrationOnly123!'}, timeout=15)
            self.assertEqual(signed.status_code, 200, signed.text)
            self.assertEqual(admin.get(base+'/api/auth/me', timeout=15).status_code, 200)
            changed = admin.patch(base+'/api/admin/site-settings', json={'area':'Integration Office'}, timeout=15)
            self.assertEqual(changed.status_code, 200, changed.text)
            self.assertIn('Integration Office', requests.get(base+'/contact', timeout=15).text)
            self.assertIn('Integration Trek', requests.get(base+'/search?q=Integration', timeout=15).text)
            self.assertEqual(admin.post(base+'/api/auth/logout', json={}, timeout=15).status_code, 200)
            self.assertEqual(admin.get(base+'/api/auth/me', timeout=15).status_code, 401)
        finally:
            process.terminate()
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
