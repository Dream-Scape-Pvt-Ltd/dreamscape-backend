import uuid

from django.test import override_settings
from rest_framework.test import APITestCase

from apps.common.lookups import ref_filter
from apps.common.testing import PortalFixtures
from apps.content_cms.models import TravelGuide, TrekGuide


class RefFilterTests(APITestCase):
    def test_uuid_becomes_pk_and_anything_else_a_slug(self):
        value = uuid.uuid4()
        self.assertEqual(ref_filter(str(value)), {'pk': value})
        self.assertEqual(ref_filter(str(value).upper(), 'trip__'), {'trip__pk': value})
        self.assertEqual(ref_filter('everest-base-camp'), {'slug': 'everest-base-camp'})
        self.assertEqual(ref_filter('1234'), {'slug': '1234'})


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SlugOrIdDetailTests(PortalFixtures, APITestCase):
    """Public pages address content by id; older links and admin tools still use slugs."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.story = TravelGuide.objects.create(title='Everest permits', slug='everest-permits', country='NEPAL',
            category='TRAVEL_TIPS', markdown_content='Permits', is_published=True)
        cls.draft_story = TravelGuide.objects.create(title='Draft', slug='draft-story', country='NEPAL',
            category='TRAVEL_TIPS', markdown_content='Draft')
        cls.guide = TrekGuide.objects.create(name='Pemba', slug='pemba', is_published=True)
        cls.draft_guide = TrekGuide.objects.create(name='Hidden', slug='hidden')

    def assert_same_by_slug_and_id(self, base, obj):
        by_slug = self.client.get(f'{base}{obj.slug}/')
        by_id = self.client.get(f'{base}{obj.id}/')
        self.assertEqual(by_slug.status_code, 200)
        self.assertEqual(by_id.status_code, 200)
        self.assertEqual(str(by_id.data['id']), str(obj.id))
        self.assertEqual(by_slug.data['id'], by_id.data['id'])
        self.assertEqual(self.client.get(f'{base}{uuid.uuid4()}/').status_code, 404)

    def test_trip_by_slug_or_id(self):
        self.assert_same_by_slug_and_id('/api/v1/trips/', self.trip)

    def test_trip_departures_by_id(self):
        response = self.client.get(f'/api/v1/trips/{self.trip.id}/departures/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([str(d['id']) for d in response.data['results']], [str(self.departure.id)])

    def test_destination_by_slug_or_id(self):
        self.assert_same_by_slug_and_id('/api/v1/destinations/', self.destination)

    def test_journal_post_by_slug_or_id_and_drafts_stay_hidden(self):
        self.assert_same_by_slug_and_id('/api/v1/content/guides/', self.story)
        self.assertEqual(self.client.get(f'/api/v1/content/guides/{self.draft_story.id}/').status_code, 404)

    def test_trek_guide_by_slug_or_id_and_drafts_stay_hidden(self):
        self.assert_same_by_slug_and_id('/api/v1/content/trek-guides/', self.guide)
        self.assertEqual(self.client.get(f'/api/v1/content/trek-guides/{self.draft_guide.id}/').status_code, 404)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get(f'/api/v1/content/trek-guides/{self.draft_guide.id}/').status_code, 200)

    def test_list_payloads_carry_ids_for_links(self):
        trip = self.client.get('/api/v1/trips/').data['results'][0]
        self.assertEqual(str(trip['destination_id']), str(self.destination.id))
        self.guide.treks_led.add(self.trip)
        detail = self.client.get(f'/api/v1/trips/{self.trip.id}/').data
        self.assertEqual(str(detail['trek_guides'][0]['id']), str(self.guide.id))
