from django.test import override_settings
from rest_framework.test import APITestCase
from apps.common.testing import PortalFixtures
from apps.faq.models import FAQ


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class FAQAPITests(PortalFixtures, APITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.faq = FAQ.objects.create(trip=cls.trip, question='Everest fitness?', answer='Walk daily',
                                    category='TREKKING', display_order=2)
        FAQ.objects.create(destination=cls.destination, question='Visa?', answer='Visa info',
                           category='GENERAL', display_order=1)
        FAQ.objects.create(question='Hidden?', answer='Draft', category='GENERAL', is_active=False)

    def test_context_filters_order_and_faqpage(self):
        response = self.client.get('/api/v1/faqs/?trip=everest-base-camp&category=TREKKING')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['faqs']), 1)
        self.assertEqual(response.data['schema_org']['@type'], 'FAQPage')
        self.assertEqual(response.data['schema_org']['mainEntity'][0]['name'], 'Everest fitness?')
        response = self.client.get('/api/v1/faqs/?destination=everest-nepal')
        self.assertEqual(len(response.data['faqs']), 1)
        response = self.client.get('/api/v1/faqs/')
        self.assertEqual([f['display_order'] for f in response.data['faqs']], [1, 2])

    def test_inactive_parent_trip_hides_faq(self):
        self.trip.is_active = False
        self.trip.save()
        self.assertEqual(self.client.get('/api/v1/faqs/?trip=everest-base-camp').data['faqs'], [])

    def test_admin_create_update_and_soft_delete(self):
        payload = {'question': 'Insurance?', 'answer': 'Required', 'category': 'TREKKING',
                   'trip': str(self.trip.pk), 'display_order': 3}
        self.client.force_authenticate(self.customer)
        self.assertEqual(self.client.post('/api/v1/faqs/', payload).status_code, 403)
        self.client.force_authenticate(self.admin)
        response = self.client.post('/api/v1/faqs/', payload)
        self.assertEqual(response.status_code, 201, response.data)
        path = f"/api/v1/faqs/{response.data['id']}/"
        self.assertEqual(self.client.patch(path, {'display_order': 0}).status_code, 200)
        self.assertEqual(self.client.delete(path).status_code, 204)
        self.assertTrue(FAQ.objects.filter(pk=response.data['id'], is_active=False).exists())

    def test_customer_cannot_edit_or_delete(self):
        self.client.force_authenticate(self.customer)
        path = f'/api/v1/faqs/{self.faq.pk}/'
        self.assertEqual(self.client.patch(path, {'answer': 'Changed'}).status_code, 403)
        self.assertEqual(self.client.delete(path).status_code, 403)
