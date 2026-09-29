from rest_framework.test import APITestCase
from apps.common.testing import PortalFixtures
from apps.content_cms.models import SiteSettings


class SiteSettingsTests(PortalFixtures, APITestCase):
    def test_public_defaults_and_admin_edit(self):
        url = '/api/v1/content/site-settings/'
        self.assertEqual(self.client.get(url).data['area'], 'Thamel')
        self.assertEqual(SiteSettings.objects.count(), 0)
        self.assertIn(self.client.patch(url, {'area': 'Changed'}).status_code, [401, 403])
        self.client.force_authenticate(self.admin)
        response = self.client.patch(url, {'area': 'Boudha', 'map_query': '27.72,85.36', 'map_zoom': 14}, format='json')
        self.assertEqual(response.status_code, 200)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(url).data['area'], 'Boudha')
        self.assertEqual(SiteSettings.objects.count(), 1)

    def test_zoom_validation(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.patch('/api/v1/content/site-settings/', {'map_zoom': 40}, format='json').status_code, 400)

    def test_home_photograph_is_editable_and_rejects_non_web_urls(self):
        self.client.force_authenticate(self.admin)
        url = '/api/v1/content/site-settings/'
        self.assertEqual(self.client.patch(url, {'home_image_url': 'javascript:alert(1)'}, format='json').status_code, 400)
        response = self.client.patch(url, {'home_image_url': 'https://example.com/trek.jpg', 'home_image_alt': 'Morning on the trail'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(url).data['home_image_alt'], 'Morning on the trail')

    def test_website_import_preserves_editor_changes(self):
        from django.core.management import call_command
        from apps.content_cms.models import TravelGuide
        from apps.destinations.models import Destination
        call_command('import_website_content', asset_base_url='https://example.com', publish=False)
        guide = TravelGuide.objects.get(slug='finding-your-own-pace')
        guide.title = 'Editor revision'
        guide.save()
        call_command('import_website_content', asset_base_url='https://other.example.com', publish=True)
        guide.refresh_from_db()
        self.assertEqual(guide.title, 'Editor revision')
        self.assertFalse(guide.is_published)
        self.assertTrue(guide.hero_image_url.startswith('https://example.com/'))
        self.assertTrue(Destination.objects.filter(slug='everest').exists())
