from django.test import override_settings
from rest_framework.test import APITestCase
from apps.common.testing import PortalFixtures
from apps.content_cms.models import TravelGuide, ResponsibleTravelInitiative


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ContentAPITests(PortalFixtures, APITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.guide = TravelGuide.objects.create(title='Everest permits', slug='everest-permits', country='NEPAL',
            category='PERMITS', markdown_content='Everest permits guide', destination=cls.destination,
            author=cls.admin, is_published=True)
        cls.draft = TravelGuide.objects.create(title='Draft', slug='draft', country='NEPAL',
            category='PERMITS', markdown_content='Draft content')
        cls.initiative = ResponsibleTravelInitiative.objects.create(title='Porter welfare', slug='porter-welfare',
            pillars=['Welfare'], content='Support porters', is_published=True)
        ResponsibleTravelInitiative.objects.create(title='Draft pledge', slug='draft-pledge', content='Draft')

    def test_public_catalog_filters_and_draft_visibility(self):
        response = self.client.get('/api/v1/content/guides/?country=NEPAL&category=PERMITS&destination=everest-nepal&search=Everest')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['destination']['slug'], self.destination.slug)
        self.assertEqual(self.client.get('/api/v1/content/guides/draft/').status_code, 404)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get('/api/v1/content/guides/').data['count'], 2)
        self.assertEqual(self.client.get('/api/v1/content/guides/draft/').status_code, 200)

    def test_article_breadcrumb_and_no_author_email(self):
        response = self.client.get('/api/v1/content/guides/everest-permits/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['schema_org_article']['@type'], 'Article')
        self.assertEqual(response.data['schema_org_breadcrumb']['@type'], 'BreadcrumbList')
        self.assertEqual(response.data['schema_org_breadcrumb']['itemListElement'][-1]['name'], self.guide.title)
        self.assertNotIn('email', response.data['author'])

    def test_admin_create_publish_unpublish_republish_preserves_date(self):
        payload = {'title': 'New guide', 'slug': 'new-guide', 'country': 'NEPAL', 'category': 'CULTURE',
                   'markdown_content': 'Culture', 'is_published': False}
        self.client.force_authenticate(self.customer)
        self.assertEqual(self.client.post('/api/v1/content/guides/', payload).status_code, 403)
        self.client.force_authenticate(self.admin)
        response = self.client.post('/api/v1/content/guides/', payload)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertIsNone(response.data['published_at'])
        path = '/api/v1/content/guides/new-guide/'
        response = self.client.patch(path, {'is_published': True})
        self.assertEqual(response.status_code, 200, response.data)
        published = response.data['published_at']
        self.assertIsNotNone(published)
        self.assertEqual(self.client.delete(path).status_code, 204)
        self.assertTrue(TravelGuide.objects.filter(slug='new-guide', is_published=False).exists())
        response = self.client.patch(path, {'is_published': True, 'published_at': '2000-01-01T00:00:00Z'})
        self.assertEqual(response.data['published_at'], published)

    def test_customer_cannot_edit_or_delete(self):
        self.client.force_authenticate(self.customer)
        path = '/api/v1/content/guides/everest-permits/'
        self.assertEqual(self.client.patch(path, {'title': 'Changed'}).status_code, 403)
        self.assertEqual(self.client.delete(path).status_code, 403)

    def test_responsible_travel_public_and_admin_creation(self):
        response = self.client.get('/api/v1/content/responsible-travel/')
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(self.client.get('/api/v1/content/responsible-travel/draft-pledge/').status_code, 404)
        self.assertEqual(self.client.get('/api/v1/content/responsible-travel/porter-welfare/').status_code, 200)
        self.client.force_authenticate(self.admin)
        response = self.client.post('/api/v1/content/responsible-travel/', {
            'title': 'New pledge', 'slug': 'new-pledge', 'content': 'Community', 'pillars': ['Community'],
            'is_published': True}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
