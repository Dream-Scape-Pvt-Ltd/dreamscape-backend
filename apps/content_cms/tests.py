import io
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from PIL import Image
from rest_framework.test import APITestCase
from apps.common.testing import PortalFixtures
from apps.common.models import MediaAsset
from apps.content_cms.models import BlogComment, SiteSettings, TravelGuide, ResponsibleTravelInitiative, TrekGuide


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ContentAPITests(PortalFixtures, APITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.guide = TravelGuide.objects.create(title='Everest permits', slug='everest-permits', country='NEPAL',
            category='TRAVEL_TIPS', markdown_content='Everest permits guide', destination=cls.destination,
            author=cls.admin, is_published=True)
        cls.draft = TravelGuide.objects.create(title='Draft', slug='draft', country='NEPAL',
            category='TRAVEL_TIPS', markdown_content='Draft content')
        cls.initiative = ResponsibleTravelInitiative.objects.create(title='Porter welfare', slug='porter-welfare',
            pillars=['Welfare'], content='Support porters', is_published=True)
        ResponsibleTravelInitiative.objects.create(title='Draft pledge', slug='draft-pledge', content='Draft')

    def test_public_catalog_filters_and_draft_visibility(self):
        response = self.client.get('/api/v1/content/guides/?country=NEPAL&category=TRAVEL_TIPS&destination=everest-nepal&search=Everest')
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
        payload = {'title': 'New guide', 'country': 'NEPAL', 'category': 'CULTURE',
                   'markdown_content': 'Culture', 'gallery_images': ['https://example.com/story.jpg'], 'is_published': False}
        self.client.force_authenticate(self.customer)
        self.assertEqual(self.client.post('/api/v1/content/guides/', payload, format='json').status_code, 403)
        self.client.force_authenticate(self.admin)
        response = self.client.post('/api/v1/content/guides/', payload, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['slug'], 'new-guide')
        self.assertEqual(response.data['gallery_images'], ['https://example.com/story.jpg'])
        self.assertTrue(TravelGuide.objects.filter(slug='new-guide', gallery_images=['https://example.com/story.jpg']).exists())
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

    def test_admin_writes_a_sectioned_article(self):
        self.client.force_authenticate(self.admin)
        payload = {'title': 'Namche days', 'country': 'NEPAL', 'category': 'ADVENTURE', 'sections': [
            {'heading': 'Arrival', 'body': 'We walked in.\n\n- Tea\n- Rest', 'image_url': 'https://example.com/a.jpg',
             'image_caption': 'The bazaar', 'extra': 'dropped'},
            {'heading': '', 'body': '', 'image_url': '', 'image_caption': ''},
            {'heading': 'Acclimatisation', 'body': 'A slow day.', 'image_url': '/media/b.jpg'},
        ]}
        response = self.client.post('/api/v1/content/guides/', payload, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        guide = TravelGuide.objects.get(slug='namche-days')
        # The empty card is dropped, unknown keys are stripped, and the Markdown mirror is rebuilt.
        self.assertEqual(guide.sections, [
            {'heading': 'Arrival', 'body': 'We walked in.\n\n- Tea\n- Rest', 'image_url': 'https://example.com/a.jpg',
             'image_caption': 'The bazaar'},
            {'heading': 'Acclimatisation', 'body': 'A slow day.', 'image_url': '/media/b.jpg', 'image_caption': ''},
        ])
        self.assertEqual(guide.markdown_content,
                         '## Arrival\n\nWe walked in.\n\n- Tea\n- Rest\n\n## Acclimatisation\n\nA slow day.')
        detail = self.client.get('/api/v1/content/guides/namche-days/').data
        self.assertEqual(len(detail['sections']), 2)
        self.assertIn('https://example.com/a.jpg', detail['schema_org_article']['image'])

        response = self.client.patch('/api/v1/content/guides/namche-days/',
                                     {'sections': [{'heading': 'Only', 'body': 'One now.'}]}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        guide.refresh_from_db()
        self.assertEqual(guide.markdown_content, '## Only\n\nOne now.')

    def test_article_sections_are_validated(self):
        self.client.force_authenticate(self.admin)
        base = {'title': 'Bad', 'country': 'NEPAL', 'category': 'ADVENTURE'}
        for sections in (
            [{'heading': 'x', 'image_url': 'javascript:alert(1)'}],
            [{'heading': 'x' * 201}],
            ['not a section'],
            [{'heading': str(i)} for i in range(31)],
            [],
        ):
            response = self.client.post('/api/v1/content/guides/', {**base, 'sections': sections}, format='json')
            self.assertEqual(response.status_code, 400, sections)

    def test_admin_can_permanently_delete_a_post_and_its_comments(self):
        guide = TravelGuide.objects.create(title='Gone soon', slug='gone-soon', country='NEPAL',
            category='OTHER', markdown_content='x', is_published=True)
        BlogComment.objects.create(guide=guide, author_name='Reader', body='Nice')
        self.client.force_authenticate(self.customer)
        self.assertEqual(self.client.delete('/api/v1/content/guides/gone-soon/?permanent=true').status_code, 403)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.delete('/api/v1/content/guides/gone-soon/?permanent=true').status_code, 204)
        self.assertFalse(TravelGuide.objects.filter(slug='gone-soon').exists())
        self.assertFalse(BlogComment.objects.filter(body='Nice').exists())

    def test_customer_cannot_edit_or_delete(self):
        self.client.force_authenticate(self.customer)
        path = '/api/v1/content/guides/everest-permits/'
        self.assertEqual(self.client.patch(path, {'title': 'Changed'}).status_code, 403)
        self.assertEqual(self.client.delete(path).status_code, 403)

    def test_published_blog_view_is_counted(self):
        path = '/api/v1/content/guides/everest-permits/view/'
        first = self.client.post(path)
        second = self.client.post(path)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.data['view_count'], 2)
        self.guide.refresh_from_db()
        self.assertEqual(self.guide.view_count, 2)
        self.assertEqual(self.client.post('/api/v1/content/guides/draft/view/').status_code, 404)

    def test_signed_in_customer_can_comment_and_admin_can_remove_comment(self):
        path = '/api/v1/content/guides/everest-permits/comments/'
        self.assertEqual(self.client.post(path, {'body': 'A useful article.'}, format='json').status_code, 401)

        self.client.force_authenticate(self.customer)
        response = self.client.post(path, {'body': 'A useful article.'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        comment_id = response.data['id']
        self.client.force_authenticate(None)
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]['body'], 'A useful article.')

        detail = self.client.get('/api/v1/content/guides/everest-permits/')
        self.assertEqual(detail.data['comment_count'], 1)
        self.assertEqual(len(detail.data['comments']), 1)

        self.client.force_authenticate(self.admin)
        delete_path = f'/api/v1/content/guides/everest-permits/comments/{comment_id}/'
        self.assertEqual(self.client.delete(delete_path).status_code, 204)
        self.assertFalse(BlogComment.objects.get(id=comment_id).is_active)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(path).data, [])

    def test_admin_can_upload_blog_images(self):
        self.client.force_authenticate(self.admin)
        image_bytes = io.BytesIO()
        Image.new('RGB', (24, 16), color=(32, 96, 64)).save(image_bytes, format='PNG')
        upload = SimpleUploadedFile('blog-cover.png', image_bytes.getvalue(), content_type='image/png')
        with tempfile.TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root):
            response = self.client.post(
                reverse('content_cms:guide-image-upload'),
                {'files': [upload]},
                format='multipart',
            )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(len(response.data['files']), 1)
        self.assertIn('/media/media/', response.data['files'][0]['url'])
        self.assertEqual(MediaAsset.objects.count(), 1)

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


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class TrekGuideAPITests(PortalFixtures, APITestCase):
    list_url = '/api/v1/content/trek-guides/'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.published = TrekGuide.objects.create(name='Santa Bahadur Tamang', slug='santa-bahadur-tamang',
            role='Lead trekking guide', years_experience=20, languages=['English', 'Nepali'], is_published=True)
        cls.published.regions.add(cls.destination)
        cls.published.treks_led.add(cls.trip)
        cls.draft = TrekGuide.objects.create(name='Draft Guide', slug='draft-guide')

    def test_public_sees_only_published_guides(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([g['slug'] for g in response.data['results']], ['santa-bahadur-tamang'])
        self.assertEqual(response.data['results'][0]['regions'], [{'id': str(self.destination.id), 'slug': 'everest-nepal', 'name': 'Everest Nepal'}])
        self.assertEqual(self.client.get(f'{self.list_url}draft-guide/').status_code, 404)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get(self.list_url).data['count'], 2)

    def test_detail_lists_active_treks_led(self):
        response = self.client.get(f'{self.list_url}santa-bahadur-tamang/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([t['slug'] for t in response.data['treks_led']], ['everest-base-camp'])
        self.trip.is_active = False
        self.trip.save(update_fields=['is_active'])
        self.assertEqual(self.client.get(f'{self.list_url}santa-bahadur-tamang/').data['treks_led'], [])

    def test_admin_creates_and_updates_with_slugs(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(self.list_url, {
            'name': 'Pemba Sherpa', 'slug': 'pemba-sherpa', 'languages': [' English ', 'English', 'Sherpa'],
            'regions': ['everest-nepal'], 'treks_led': ['everest-base-camp'], 'is_published': True}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['languages'], ['English', 'Sherpa'])
        self.assertEqual(response.data['treks_led'][0]['slug'], 'everest-base-camp')
        response = self.client.patch(f'{self.list_url}pemba-sherpa/', {'role': 'Assistant guide', 'regions': []}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['role'], 'Assistant guide')
        self.assertEqual(response.data['regions'], [])

    def test_rejects_bad_input_and_duplicate_slug(self):
        self.client.force_authenticate(self.admin)
        duplicate = self.client.post(self.list_url, {'name': 'Another', 'slug': 'santa-bahadur-tamang'}, format='json')
        self.assertEqual(duplicate.status_code, 400)
        bad = self.client.post(self.list_url, {'name': 'X', 'slug': 'x', 'languages': 'English', 'treks_led': ['no-such-trek']}, format='json')
        self.assertEqual(bad.status_code, 400)

    def test_customers_cannot_write(self):
        self.client.force_authenticate(self.customer)
        self.assertEqual(self.client.post(self.list_url, {'name': 'X', 'slug': 'x'}, format='json').status_code, 403)
        self.assertEqual(self.client.delete(f'{self.list_url}santa-bahadur-tamang/').status_code, 403)

    def test_delete_unpublishes_unless_permanent(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.delete(f'{self.list_url}santa-bahadur-tamang/').status_code, 204)
        self.published.refresh_from_db()
        self.assertFalse(self.published.is_published)
        self.assertEqual(self.client.delete(f'{self.list_url}santa-bahadur-tamang/?permanent=true').status_code, 204)
        self.assertFalse(TrekGuide.objects.filter(slug='santa-bahadur-tamang').exists())

    def test_trip_detail_names_its_published_guides(self):
        response = self.client.get(f'/api/v1/trips/{self.trip.slug}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([g['slug'] for g in response.data['trek_guides']], ['santa-bahadur-tamang'])


class SiteSettingsAPITests(PortalFixtures, APITestCase):
    url = '/api/v1/content/site-settings/'

    def test_public_read_is_empty_until_saved_and_never_shows_crm_hours(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['data'], {})
        SiteSettings.objects.create(content={'home_title': 'Walk higher'}, crm_sla_hours=6)
        data = self.client.get(self.url).json()['data']
        self.assertEqual(data, {'home_title': 'Walk higher'})

    def test_admin_saves_content_and_response_time(self):
        self.client.force_authenticate(self.admin)
        payload = {'home_title': 'Walk higher', 'nav_company_items': [{'label': 'About Us', 'description': 'Our story', 'href': '/about'}], 'crm_sla_hours': 6}
        response = self.client.patch(self.url, payload, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['data']['crm_sla_hours'], 6)
        row = SiteSettings.load()
        self.assertEqual((row.content['home_title'], row.crm_sla_hours), ('Walk higher', 6))
        self.assertNotIn('crm_sla_hours', row.content)
        # The editor always sends the whole object, so a save replaces the content.
        self.client.patch(self.url, {'home_title': 'Beyond the horizon'}, format='json')
        row.refresh_from_db()
        self.assertEqual((row.content, row.crm_sla_hours), ({'home_title': 'Beyond the horizon'}, 6))

    def test_invalid_response_time_and_non_object_bodies_are_rejected(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.patch(self.url, {'crm_sla_hours': 0}, format='json').status_code, 400)
        self.assertEqual(self.client.patch(self.url, {'crm_sla_hours': '4'}, format='json').status_code, 400)
        self.assertEqual(self.client.patch(self.url, ['not', 'an', 'object'], format='json').status_code, 400)

    def test_customers_cannot_change_settings(self):
        self.client.force_authenticate(self.customer)
        self.assertEqual(self.client.patch(self.url, {'home_title': 'Hijacked'}, format='json').status_code, 403)
        self.assertFalse(SiteSettings.objects.exists())
