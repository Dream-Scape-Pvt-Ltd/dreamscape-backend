from rest_framework.test import APITestCase
from apps.common.testing import PortalFixtures
from apps.content_cms.models import TrekGuide

class TrekGuideProfileTests(PortalFixtures,APITestCase):
    def test_draft_stays_private_and_public_uuid_and_slug_work(self):
        url='/api/v1/content/trek-guides/'
        self.assertIn(self.client.post(url,{'name':'Actual guide','slug':'actual-guide'},format='json').status_code,[401,403])
        self.client.force_authenticate(self.admin)
        response=self.client.post(url,{'name':'Actual guide','slug':'actual-guide','bio':'Approved biography','languages':['Nepali'],'regions':[self.destination.slug],'treks_led':[self.trip.slug]},format='json')
        self.assertEqual(response.status_code,201)
        guide_id=response.data['id']
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(url).data['count'],0)
        self.assertEqual(self.client.get(f"/api/v1/trips/{self.trip.slug}/").data["trek_guides"],[])
        self.assertEqual(self.client.get(url+str(guide_id)+'/').status_code,404)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.patch(url+'actual-guide/',{'is_published':True},format='json').status_code,200)
        self.client.force_authenticate(None)
        public=self.client.get(url+str(guide_id)+'/')
        self.assertEqual(public.status_code,200)
        self.assertEqual(self.client.get(f"/api/v1/trips/{self.trip.slug}/").data["trek_guides"][0]["slug"],"actual-guide")
        self.assertEqual(public.data['regions'][0]['id'],str(self.destination.pk))
        self.assertEqual(public.data['treks_led'][0]['slug'],self.trip.slug)
        self.assertEqual(self.client.get(url+'actual-guide/').status_code,200)
        self.trip.is_active=False;self.trip.save(update_fields=['is_active'])
        self.assertEqual(self.client.get(url+'actual-guide/').data['treks_led'],[])

    def test_rejects_unsafe_photos_and_non_admin_edits_and_unpublishes(self):
        guide=TrekGuide.objects.create(name='Actual guide',slug='actual-guide',is_published=True)
        url='/api/v1/content/trek-guides/actual-guide/'
        self.client.force_authenticate(self.customer)
        self.assertEqual(self.client.patch(url,{'bio':'Changed'},format='json').status_code,403)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.patch(url,{'photo_url':'javascript:alert(1)'},format='json').status_code,400)
        self.assertEqual(self.client.delete(url).status_code,204)
        guide.refresh_from_db();self.assertFalse(guide.is_published)
