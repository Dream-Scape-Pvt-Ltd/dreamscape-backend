from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import UserRole
from apps.destinations.models import ActivityCategory, Destination, DestinationCountry

User = get_user_model()


class DestinationTests(APITestCase):
    """
    Test suite for Destinations & Activity Categories endpoints.
    """

    def setUp(self):
        self.admin = User.objects.create_superuser(
            email="admin@dreamscapetreks.com",
            password="SecureAdminPassword123!",
            first_name="Admin",
            last_name="Superuser",
        )
        self.customer = User.objects.create_user(
            email="traveler@example.com",
            password="SecurePassword123!",
            first_name="Trekker",
            last_name="User",
            role=UserRole.CUSTOMER,
        )

        self.category = ActivityCategory.objects.create(
            name="Classic Trekking",
            slug="classic-trekking",
            description="High mountain lodge-to-lodge journeys.",
        )

        self.destination = Destination.objects.create(
            name="Everest Region",
            slug="everest-region",
            country=DestinationCountry.NEPAL,
            region_name="Khumbu",
            visa_guidelines="On-arrival visa available at Tribhuvan International Airport (KTM).",
            permit_details="Sagarmatha National Park Permit and Khumbu Pasang Lhamu Rural Municipality Permit required.",
            hero_media="https://images.dreamscapetreks.com/everest-hero.webp",
        )

    def test_list_destinations_public(self):
        url = reverse("destinations:destination-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        res = response.json()
        self.assertTrue(res["success"])
        self.assertGreaterEqual(len(res["data"]["results"]), 1)
        first = res["data"]["results"][0]
        self.assertEqual(first["slug"], "everest-region")
        self.assertIn("trips_count", first)

    def test_create_destination_as_admin(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse("destinations:destination-list")
        payload = {
            "name": "Annapurna Sanctuary",
            "slug": "annapurna-sanctuary",
            "country": DestinationCountry.NEPAL,
            "region_name": "Gandaki",
            "visa_guidelines": "Nepal on-arrival tourist visa.",
            "permit_details": "ACAP permit and TIMS card.",
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        res = response.json()
        self.assertTrue(res["success"])
        self.assertEqual(res["data"]["slug"], "annapurna-sanctuary")

    def test_create_destination_as_customer_forbidden(self):
        self.client.force_authenticate(user=self.customer)
        url = reverse("destinations:destination-list")
        payload = {
            "name": "Langtang Valley",
            "slug": "langtang-valley",
            "country": DestinationCountry.NEPAL,
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        res = response.json()
        self.assertFalse(res["success"])

    def test_get_destination_detail(self):
        url = reverse("destinations:destination-detail", kwargs={"slug": self.destination.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        res = response.json()
        self.assertTrue(res["success"])
        self.assertEqual(res["data"]["slug"], "everest-region")
        self.assertIn("permit_details", res["data"])
        self.assertIn("schema_org_json_ld", res["data"])
        self.assertEqual(res["data"]["schema_org_json_ld"]["@type"], "TouristDestination")

    def test_patch_destination_as_admin(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse("destinations:destination-detail", kwargs={"slug": self.destination.slug})
        response = self.client.patch(url, {"region_name": "Solukhumbu High Himalaya"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        res = response.json()
        self.assertEqual(res["data"]["region_name"], "Solukhumbu High Himalaya")

    def test_list_and_create_categories(self):
        # Public GET
        list_url = reverse("destinations:category-list")
        response = self.client.get(list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        res = response.json()
        self.assertTrue(res["success"])

        # Admin POST
        self.client.force_authenticate(user=self.admin)
        payload = {
            "name": "Mountaineering Expeditions",
            "slug": "mountaineering-expeditions",
            "description": "Technical 7,000m and 8,000m summit climbs.",
        }
        post_response = self.client.post(list_url, payload, format="json")
        self.assertEqual(post_response.status_code, status.HTTP_201_CREATED)
        res_post = post_response.json()
        self.assertEqual(res_post["data"]["slug"], "mountaineering-expeditions")
