from django.test import override_settings
from rest_framework.test import APITestCase
from apps.common.testing import PortalFixtures
from apps.content_cms.models import TravelGuide
from apps.faq.models import FAQ


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SearchAPITests(PortalFixtures, APITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        TravelGuide.objects.create(title='Everest guide', slug='everest-guide', country='NEPAL',
                                   category='PERMITS', markdown_content='Everest', is_published=True)
        TravelGuide.objects.create(title='Everest draft', slug='everest-draft', country='NEPAL',
                                   category='PERMITS', markdown_content='Everest')
        FAQ.objects.create(question='Everest permits?', answer='Permit needed', category='TREKKING')
        FAQ.objects.create(question='Everest hidden?', answer='Draft', category='TREKKING', is_active=False)

    def test_cross_entity_ranking_and_metadata(self):
        response = self.client.get('/api/v1/search/?q=everest')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['count'], 4)
        results = response.data['results']
        self.assertEqual({r['entity_type'] for r in results}, {'trip', 'destination', 'guide', 'faq'})
        ranks = [r['rank_score'] for r in results]
        self.assertEqual(ranks, sorted(ranks, reverse=True))
        self.assertIn('duration_days', next(r['meta'] for r in results if r['entity_type'] == 'trip'))

    def test_entity_filter_and_true_pagination(self):
        response = self.client.get('/api/v1/search/?q=everest&entity_type=guide')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['count'], 1)
        first = self.client.get('/api/v1/search/?q=everest&page_size=2')
        second = self.client.get('/api/v1/search/?q=everest&page_size=2&page=2')
        self.assertEqual(first.data['count'], 4)
        self.assertEqual(len(second.data['results']), 2)
        self.assertIsNotNone(first.data['next'])
        self.assertIsNotNone(second.data['previous'])
        self.assertFalse({r['id'] for r in first.data['results']} & {r['id'] for r in second.data['results']})

    def test_query_validation_and_empty_results(self):
        for query in ['', '?q=e', '?q=%20%20', '?q=everest&entity_type=unknown',
                      '?q=everest&page=0', '?q=everest&page_size=101']:
            self.assertEqual(self.client.get('/api/v1/search/' + query).status_code, 400)
        response = self.client.get('/api/v1/search/?q=nomatchxyz')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 0)

    def test_no_draft_leak_even_for_admin(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get('/api/v1/search/?q=draft')
        self.assertEqual(response.data['count'], 0)

    def test_throttle_applies_to_authenticated_users(self):
        self.client.force_authenticate(self.customer)
        from apps.search.views.search_views import SearchIPThrottle
        from unittest.mock import patch
        with patch.object(SearchIPThrottle, 'get_rate', return_value='1/minute'):
            self.assertEqual(self.client.get('/api/v1/search/?q=everest').status_code, 200)
            self.assertEqual(self.client.get('/api/v1/search/?q=everest').status_code, 429)
