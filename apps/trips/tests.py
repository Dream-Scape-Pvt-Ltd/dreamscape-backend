import datetime
import io
import tempfile
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import UserRole
from apps.common.models import MediaAsset
from apps.destinations.models import ActivityCategory, Destination, DestinationCountry
from apps.trips.models import (
    AccommodationType,
    DepartureStatus,
    DifficultyGrade,
    ItineraryDay,
    Trip,
    TripDeparture,
    TripReview,
)

User = get_user_model()


class TripCatalogTests(APITestCase):
    """
    Comprehensive test suite for Phase 2: Trips, Itineraries, Departures, Reviews & Expedition Details.
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
            description="Lodge treks.",
        )

        self.destination = Destination.objects.create(
            name="Everest Region",
            slug="everest-region",
            country=DestinationCountry.NEPAL,
            region_name="Khumbu",
        )

        self.trip = Trip.objects.create(
            destination=self.destination,
            category=self.category,
            title="Everest Base Camp Trek",
            slug="everest-base-camp-trek",
            duration_days=14,
            altitude_max_meters=5364,
            difficulty_grade=DifficultyGrade.GRADE_3,
            min_group_size=2,
            max_group_size=12,
            best_seasons=["Spring", "Autumn"],
            starting_price_usd=1650.00,
            overview="Iconic Himalayan trek to the foot of Mt. Everest.",
            is_featured=True,
            is_active=True,
        )

        self.day1 = ItineraryDay.objects.create(
            trip=self.trip,
            day_number=1,
            title="Fly Kathmandu to Lukla, Trek to Phakding",
            description="Scenic mountain flight followed by easy downhill trail.",
            overnight_stay="Phakding",
            elevation_meters=2610,
            accommodation_type=AccommodationType.TEAHOUSE,
            latitude=27.7408,
            longitude=86.7118,
        )

        self.today = datetime.date.today()
        self.departure = TripDeparture.objects.create(
            trip=self.trip,
            start_date=self.today + datetime.timedelta(days=30),
            end_date=self.today + datetime.timedelta(days=44),
            price_usd=1650.00,
            max_seats=12,
            available_seats=10,
            status=DepartureStatus.GUARANTEED,
            is_guaranteed=True,
        )

    def test_list_trips_and_filters(self):
        url = reverse("trips:trip-list")

        # Basic GET
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        res = response.json()
        self.assertTrue(res["success"])
        self.assertEqual(res["data"]["count"], 1)
        self.assertEqual(res["data"]["results"][0]["slug"], "everest-base-camp-trek")

        # Filter by destination slug
        res_dest = self.client.get(f"{url}?destination=everest-region").json()
        self.assertEqual(res_dest["data"]["count"], 1)

        # Filter by nonexistent destination
        res_empty = self.client.get(f"{url}?destination=nonexistent").json()
        self.assertEqual(res_empty["data"]["count"], 0)

        # Filter by price range
        res_price = self.client.get(f"{url}?min_price=1000&max_price=2000").json()
        self.assertEqual(res_price["data"]["count"], 1)

        # Filter by difficulty
        res_diff = self.client.get(f"{url}?difficulty_grade=GRADE_3").json()
        self.assertEqual(res_diff["data"]["count"], 1)

        # Filter by season
        res_season = self.client.get(f"{url}?season=Spring").json()
        self.assertEqual(res_season["data"]["count"], 1)

    def test_create_trip_as_admin(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse("trips:trip-list")
        payload = {
            "destination": str(self.destination.id),
            "category": str(self.category.id),
            "title": "Gokyo Lakes & Cho La Pass",
            "slug": "gokyo-lakes-cho-la-pass",
            "duration_days": 16,
            "altitude_max_meters": 5420,
            "difficulty_grade": DifficultyGrade.GRADE_4,
            "starting_price_usd": "1890.00",
            "overview": "High passes and turquoise glacial lakes.",
            "is_active": True,
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        res = response.json()
        self.assertTrue(res["success"])
        self.assertEqual(res["data"]["slug"], "gokyo-lakes-cho-la-pass")

    def test_create_trip_as_customer_forbidden(self):
        self.client.force_authenticate(user=self.customer)
        url = reverse("trips:trip-list")
        payload = {
            "destination": str(self.destination.id),
            "category": str(self.category.id),
            "title": "Unauthorized Trip",
            "slug": "unauthorized-trip",
            "duration_days": 5,
            "difficulty_grade": DifficultyGrade.GRADE_1,
            "starting_price_usd": "500.00",
            "overview": "Should be rejected.",
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        res = response.json()
        self.assertFalse(res["success"])

    def test_admin_can_upload_trek_images(self):
        self.client.force_authenticate(user=self.admin)
        image_bytes = io.BytesIO()
        Image.new("RGB", (24, 16), color=(32, 96, 64)).save(image_bytes, format="PNG")
        upload = SimpleUploadedFile(
            "everest-cover.png",
            image_bytes.getvalue(),
            content_type="image/png",
        )

        with tempfile.TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root):
            response = self.client.post(
                reverse("trips:trip-image-upload"),
                {"files": [upload]},
                format="multipart",
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(len(payload["data"]["files"]), 1)
        self.assertIn("/media/media/", payload["data"]["files"][0]["url"])
        self.assertEqual(MediaAsset.objects.count(), 1)

    def test_customer_cannot_upload_trek_images(self):
        self.client.force_authenticate(user=self.customer)
        response = self.client.post(
            reverse("trips:trip-image-upload"),
            {},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_trip_detail_with_schema_org(self):
        url = reverse("trips:trip-detail", kwargs={"slug": self.trip.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        res = response.json()
        self.assertTrue(res["success"])
        trip_data = res["data"]
        self.assertEqual(trip_data["slug"], "everest-base-camp-trek")
        self.assertEqual(len(trip_data["itinerary_days"]), 1)
        self.assertEqual(len(trip_data["departures"]), 1)
        self.assertIn("schema_org_json_ld", trip_data)
        self.assertEqual(trip_data["schema_org_json_ld"]["@type"], "TouristTrip")

    def test_itinerary_list_and_create(self):
        list_url = reverse("trips:trip-itinerary", kwargs={"slug": self.trip.slug})

        # Public GET
        response = self.client.get(list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        res = response.json()
        self.assertTrue(res["success"])
        self.assertEqual(len(res["data"]["results"]), 1)

        # Admin POST Day 2
        self.client.force_authenticate(user=self.admin)
        payload = {
            "day_number": 2,
            "title": "Trek Phakding to Namche Bazaar",
            "description": "Enter Sagarmatha National Park and climb up to Sherpa capital.",
            "overnight_stay": "Namche Bazaar",
            "elevation_meters": 3440,
            "accommodation_type": AccommodationType.TEAHOUSE,
            "is_acclimatization_day": False,
            "latitude": 27.8069,
            "longitude": 86.7140,
        }
        post_response = self.client.post(list_url, payload, format="json")
        self.assertEqual(post_response.status_code, status.HTTP_201_CREATED)
        res_post = post_response.json()
        self.assertEqual(res_post["data"]["day_number"], 2)

    def test_departure_list_and_create(self):
        list_url = reverse("trips:departure-list", kwargs={"slug": self.trip.slug})

        # Public GET
        response = self.client.get(list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        res = response.json()
        self.assertTrue(res["success"])
        self.assertEqual(len(res["data"]["results"]), 1)

        # Admin POST new departure
        self.client.force_authenticate(user=self.admin)
        payload = {
            "start_date": str(self.today + datetime.timedelta(days=60)),
            "end_date": str(self.today + datetime.timedelta(days=74)),
            "price_usd": "1700.00",
            "max_seats": 14,
            "available_seats": 14,
            "status": DepartureStatus.LIMITED,
        }
        post_response = self.client.post(list_url, payload, format="json")
        self.assertEqual(post_response.status_code, status.HTTP_201_CREATED)
        res_post = post_response.json()
        self.assertEqual(res_post["data"]["max_seats"], 14)

    def test_review_submission_and_moderation(self):
        reviews_url = reverse("trips:review-list", kwargs={"slug": self.trip.slug})

        # Submit customer review
        review_payload = {
            "reviewer_name": "Edmund H.",
            "reviewer_country": "New Zealand",
            "rating_overall": 5,
            "rating_guide": 5,
            "rating_itinerary": 5,
            "rating_safety": 5,
            "title": "Unforgettable Journey",
            "content": "Flawless organization, legendary Sherpa team!",
            "travel_date": "2026-05-01",
        }
        post_response = self.client.post(reviews_url, review_payload, format="json")
        self.assertEqual(post_response.status_code, status.HTTP_201_CREATED)
        res_post = post_response.json()
        review_id = res_post["data"]["id"]

        # Public listing should NOT show unmoderated review yet
        get_response = self.client.get(reviews_url)
        self.assertEqual(get_response.json()["data"]["count"], 0)

        # Admin moderates and publishes review
        self.client.force_authenticate(user=self.admin)
        mod_url = reverse("trips:review-moderation", kwargs={"slug": self.trip.slug, "review_id": review_id})
        patch_response = self.client.patch(mod_url, {"is_published": True, "is_verified": True}, format="json")
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)

        # Public listing now includes the approved review
        self.client.logout()
        updated_get = self.client.get(reviews_url)
        self.assertEqual(updated_get.json()["data"]["count"], 1)

    def test_expedition_detail_create_and_get(self):
        exp_url = reverse("trips:expedition-detail", kwargs={"slug": self.trip.slug})

        # Initial GET returns 404 since no expedition detail attached yet
        get_response = self.client.get(exp_url)
        self.assertEqual(get_response.status_code, status.HTTP_404_NOT_FOUND)

        # Admin creates expedition detail
        self.client.force_authenticate(user=self.admin)
        payload = {
            "summit_window": "Late April to Mid May",
            "technical_rating": "Alpine Grade III, 50-degree ice slopes",
            "gear_requirements": ["Crampons", "Ice axe", "Harness", "Ascender / Jumar"],
            "permit_fee_type": "NMA Peak Permit",
            "mandatory_certifications": ["Basic Mountaineering Course (BMC)"],
        }
        post_response = self.client.post(exp_url, payload, format="json")
        self.assertEqual(post_response.status_code, status.HTTP_201_CREATED)
        res_post = post_response.json()
        self.assertEqual(res_post["data"]["summit_window"], "Late April to Mid May")

        # Subsequent GET returns 200 OK
        self.client.logout()
        final_get = self.client.get(exp_url)
        self.assertEqual(final_get.status_code, status.HTTP_200_OK)


class TripHighlightTests(APITestCase):
    """
    Test suite for Trip Highlights endpoint (/api/v1/trips/highlights/).
    Tests public retrieval (with featured fallback) and Admin curation of up to 5 trips.
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
            slug="classic-trekking-hl",
        )
        self.destination = Destination.objects.create(
            name="Everest Region",
            slug="everest-region-hl",
            country=DestinationCountry.NEPAL,
            region_name="Khumbu",
        )

        # Create 6 active trips and 1 inactive trip
        self.trips = []
        for i in range(1, 7):
            trip = Trip.objects.create(
                destination=self.destination,
                category=self.category,
                title=f"Himalayan Trek {i}",
                slug=f"himalayan-trek-{i}",
                duration_days=10 + i,
                altitude_max_meters=4000 + i * 200,
                difficulty_grade=DifficultyGrade.GRADE_2,
                min_group_size=2,
                max_group_size=12,
                starting_price_usd=1200.00 + i * 100,
                overview=f"Overview for Trek {i}",
                is_featured=(i <= 3),  # First 3 are featured
                is_active=True,
            )
            self.trips.append(trip)

        self.inactive_trip = Trip.objects.create(
            destination=self.destination,
            category=self.category,
            title="Inactive Trek",
            slug="inactive-trek",
            duration_days=5,
            altitude_max_meters=3000,
            difficulty_grade=DifficultyGrade.GRADE_1,
            starting_price_usd=800.00,
            overview="Not currently active.",
            is_active=False,
        )

        self.highlights_url = reverse("trips:trip-highlights")

    def test_get_highlights_fallback_to_featured(self):
        """When no trips are explicitly highlighted, fallback to featured trips."""
        response = self.client.get(self.highlights_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()["data"]
        self.assertEqual(len(data), 3)  # 3 featured trips
        slugs = [t["slug"] for t in data]
        self.assertIn("himalayan-trek-1", slugs)
        self.assertIn("himalayan-trek-2", slugs)
        self.assertIn("himalayan-trek-3", slugs)

    def test_admin_set_highlights_up_to_5_trips(self):
        """Admin can curate up to 5 highlighted trips in specific display order."""
        self.client.force_authenticate(user=self.admin)
        selected_ids = [str(t.id) for t in self.trips[:5]]

        payload = {"trip_ids": selected_ids}
        response = self.client.put(self.highlights_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()["data"]
        self.assertEqual(len(data), 5)
        # Verify order and is_highlighted
        for idx, item in enumerate(data, start=1):
            self.assertTrue(item["is_highlighted"])
            self.assertEqual(item["highlight_order"], idx)
            self.assertEqual(item["id"], selected_ids[idx - 1])

        # Verify public GET returns these 5 highlights
        self.client.logout()
        get_res = self.client.get(self.highlights_url)
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)
        get_data = get_res.json()["data"]
        self.assertEqual(len(get_data), 5)
        self.assertEqual([t["id"] for t in get_data], selected_ids)

    def test_admin_set_highlights_using_slugs(self):
        """Admin can curate highlighted trips using trip slugs."""
        self.client.force_authenticate(user=self.admin)
        selected_slugs = [self.trips[4].slug, self.trips[2].slug, self.trips[0].slug]

        payload = {"trip_slugs": selected_slugs}
        response = self.client.post(self.highlights_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()["data"]
        self.assertEqual(len(data), 3)
        self.assertEqual(data[0]["slug"], self.trips[4].slug)
        self.assertEqual(data[0]["highlight_order"], 1)
        self.assertEqual(data[1]["slug"], self.trips[2].slug)
        self.assertEqual(data[1]["highlight_order"], 2)
        self.assertEqual(data[2]["slug"], self.trips[0].slug)
        self.assertEqual(data[2]["highlight_order"], 3)

    def test_reject_more_than_5_trips(self):
        """Attempting to highlight more than 5 trips triggers validation error."""
        self.client.force_authenticate(user=self.admin)
        payload = {"trip_ids": [str(t.id) for t in self.trips[:6]]}  # 6 trips

        response = self.client.put(self.highlights_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        error = response.json()["error"]
        self.assertTrue("5" in str(error) and "trip_ids" in str(error))

    def test_reject_duplicate_trips(self):
        """Duplicate trips in payload are rejected."""
        self.client.force_authenticate(user=self.admin)
        duplicate_ids = [str(self.trips[0].id), str(self.trips[0].id)]
        payload = {"trip_ids": duplicate_ids}

        response = self.client.put(self.highlights_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reject_inactive_trip(self):
        """Inactive trips cannot be highlighted."""
        self.client.force_authenticate(user=self.admin)
        payload = {"trip_ids": [str(self.inactive_trip.id)]}

        response = self.client.put(self.highlights_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_permissions_unauthenticated_and_customer(self):
        """Unauthenticated and customer requests cannot modify highlights."""
        payload = {"trip_ids": [str(self.trips[0].id)]}

        # Anonymous
        anon_res = self.client.put(self.highlights_url, payload, format="json")
        self.assertEqual(anon_res.status_code, status.HTTP_401_UNAUTHORIZED)

        # Customer
        self.client.force_authenticate(user=self.customer)
        cust_res = self.client.put(self.highlights_url, payload, format="json")
        self.assertEqual(cust_res.status_code, status.HTTP_403_FORBIDDEN)

    def test_highlight_replacement_cleans_old_highlights(self):
        """Updating highlights completely replaces previous highlight assignments."""
        self.client.force_authenticate(user=self.admin)

        # Initial set: trip 0 and trip 1
        self.client.put(self.highlights_url, {"trip_ids": [str(self.trips[0].id), str(self.trips[1].id)]}, format="json")
        self.assertEqual(Trip.objects.filter(is_highlighted=True).count(), 2)

        # Replace with trip 3
        self.client.put(self.highlights_url, {"trip_ids": [str(self.trips[3].id)]}, format="json")
        self.assertEqual(Trip.objects.filter(is_highlighted=True).count(), 1)

        self.trips[0].refresh_from_db()
        self.trips[1].refresh_from_db()
        self.trips[3].refresh_from_db()

        self.assertFalse(self.trips[0].is_highlighted)
        self.assertIsNone(self.trips[0].highlight_order)
        self.assertFalse(self.trips[1].is_highlighted)
        self.assertIsNone(self.trips[1].highlight_order)
        self.assertTrue(self.trips[3].is_highlighted)
        self.assertEqual(self.trips[3].highlight_order, 1)
