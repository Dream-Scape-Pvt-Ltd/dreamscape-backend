import re
from datetime import date, timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import UserRole
from apps.destinations.models import Destination, ActivityCategory, DestinationCountry
from apps.inquiries.models import Inquiry, InquiryNote, InquiryStatus, InquiryType, TailorMadeRequest
from apps.trips.models import DifficultyGrade, DepartureStatus, Trip, TripDeparture

User = get_user_model()


class InquiryAPITests(APITestCase):
    def setUp(self):
        # Create users: Admin, Sales Agent, and Customer
        self.admin_user = User.objects.create_user(
            email="admin@dreamscapetreks.com",
            password="AdminPassword123!",
            first_name="Admin",
            last_name="User",
            role=UserRole.ADMIN,
            is_staff=True,
        )
        self.agent_user = User.objects.create_user(
            email="agent@dreamscapetreks.com",
            password="AgentPassword123!",
            first_name="Karma",
            last_name="Sherpa",
            role=UserRole.SALES_AGENT,
            is_staff=True,
        )
        self.customer_user = User.objects.create_user(
            email="traveler@example.com",
            password="TravelerPass123!",
            first_name="John",
            last_name="Doe",
            role=UserRole.CUSTOMER,
        )

        # Create destination, category, trip, departure
        self.destination = Destination.objects.create(
            name="Nepal Himalayas",
            slug="nepal-himalayas",
            country=DestinationCountry.NEPAL,
        )
        self.category = ActivityCategory.objects.create(
            name="Classic Treks",
            slug="classic-treks",
        )
        self.trip = Trip.objects.create(
            destination=self.destination,
            category=self.category,
            title="Annapurna Circuit Trek",
            slug="annapurna-circuit-trek",
            duration_days=16,
            difficulty_grade=DifficultyGrade.GRADE_3,
            starting_price_usd=Decimal("1800.00"),
            overview="Classic Annapurna loop crossing Thorong La.",
        )
        self.start_date = date.today() + timedelta(days=45)
        self.departure = TripDeparture.objects.create(
            trip=self.trip,
            start_date=self.start_date,
            end_date=self.start_date + timedelta(days=16),
            price_usd=Decimal("1800.00"),
            max_seats=12,
            available_seats=12,
            status=DepartureStatus.GUARANTEED,
        )

    def test_public_general_inquiry_submission_success(self):
        """Public user can submit a general inquiry without authentication."""
        url = reverse("inquiries:inquiry-list-create")
        payload = {
            "inquiry_type": InquiryType.GENERAL,
            "full_name": "Maya Lin",
            "email": "maya.lin@example.com",
            "phone": "+1-555-0199",
            "message": "Interested in private departures for a family group in Autumn.",
            "preferred_dates": "October 2026",
            "estimated_budget": "5000.00",
            "group_size": 4,
        }

        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        res_json = response.json()
        self.assertTrue(res_json["success"])

        data = res_json["data"]
        self.assertRegex(data["inquiry_number"], r"^INQ-\d{4}-\d{4}$")
        self.assertEqual(data["inquiry_type"], InquiryType.GENERAL)
        self.assertEqual(data["full_name"], "Maya Lin")
        self.assertEqual(data["status"], InquiryStatus.NEW)

        # Verify database record
        inquiry = Inquiry.objects.get(inquiry_number=data["inquiry_number"])
        self.assertEqual(inquiry.email, "maya.lin@example.com")
        self.assertEqual(inquiry.group_size, 4)

    def test_public_tailor_made_inquiry_atomic_creation(self):
        """Tailor-made inquiry atomically creates both Inquiry and TailorMadeRequest."""
        url = reverse("inquiries:inquiry-list-create")
        payload = {
            "inquiry_type": InquiryType.TAILOR_MADE,
            "full_name": "Alexander von Humboldt",
            "email": "humboldt@explorer.org",
            "phone": "+49-30-123456",
            "message": "Custom high-altitude botanical and photography expedition.",
            "preferred_dates": "May 2026",
            "estimated_budget": "12000.00",
            "group_size": 2,
            "tailor_made": {
                "custom_destinations": ["Everest Gokyo Lakes", "Cho La Pass", "Renjo La Pass"],
                "desired_activities": ["High-altitude photography", "Glacial study", "Boutique lodges"],
                "fitness_level": "Advanced / Marathon runner",
                "accommodation_standard": "Luxury & Boutique Teahouse",
                "guide_language_preference": "German and English",
                "custom_route_coordinates": [
                    {"name": "Lukla", "lat": 27.6869, "lng": 86.7297, "alt_m": 2840},
                    {"name": "Gokyo", "lat": 27.9542, "lng": 86.6953, "alt_m": 4790},
                ],
                "waypoints": ["Gokyo Ri Sunrise", "Renjo La Summit Panorama"],
            },
        }

        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()["data"]

        self.assertRegex(data["inquiry_number"], r"^INQ-\d{4}-\d{4}$")
        self.assertEqual(data["inquiry_type"], InquiryType.TAILOR_MADE)

        # Check nested tailor_made_detail in response
        tm_detail = data.get("tailor_made_detail")
        self.assertIsNotNone(tm_detail)
        self.assertEqual(tm_detail["fitness_level"], "Advanced / Marathon runner")
        self.assertEqual(len(tm_detail["custom_destinations"]), 3)
        self.assertEqual(len(tm_detail["custom_route_coordinates"]), 2)

        # Check DB record
        inquiry = Inquiry.objects.get(inquiry_number=data["inquiry_number"])
        self.assertTrue(hasattr(inquiry, "tailor_made_detail"))
        self.assertEqual(inquiry.tailor_made_detail.guide_language_preference, "German and English")

    def test_journey_specific_inquiry_with_departure(self):
        """Journey inquiry links foreign keys to Trip and TripDeparture."""
        url = reverse("inquiries:inquiry-list-create")
        payload = {
            "inquiry_type": InquiryType.JOURNEY,
            "trip": str(self.trip.id),
            "departure": str(self.departure.id),
            "full_name": "Tenzing Traveler",
            "email": "tenzing@example.com",
            "message": "Do you offer single supplement tents on this departure?",
            "group_size": 1,
        }

        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()["data"]

        self.assertEqual(data["trip_title"], "Annapurna Circuit Trek")
        self.assertIsNotNone(data["departure"])
        self.assertEqual(data["departure"]["price_usd"], "1800.00")

    def test_rbac_inquiry_list_forbidden_for_customers(self):
        """Customers and anonymous users cannot view CRM inquiries (401/403)."""
        url = reverse("inquiries:inquiry-list-create")

        # Anonymous -> 401
        res_anon = self.client.get(url)
        self.assertEqual(res_anon.status_code, status.HTTP_401_UNAUTHORIZED)

        # Customer -> 403 Forbidden
        self.client.force_authenticate(user=self.customer_user)
        res_cust = self.client.get(url)
        self.assertEqual(res_cust.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(res_cust.json()["success"])
        self.assertEqual(res_cust.json()["error"]["code"], "FORBIDDEN")

    def test_rbac_inquiry_list_accessible_to_agents_and_admins(self):
        """Sales agents and admins can view the CRM lead pipeline."""
        Inquiry.objects.create(
            inquiry_number="INQ-2026-1111",
            inquiry_type=InquiryType.GENERAL,
            full_name="Lead One",
            email="lead1@example.com",
            status=InquiryStatus.NEW,
        )
        Inquiry.objects.create(
            inquiry_number="INQ-2026-2222",
            inquiry_type=InquiryType.TAILOR_MADE,
            full_name="Lead Two",
            email="lead2@example.com",
            status=InquiryStatus.IN_CONTACT,
            assigned_agent=self.agent_user,
        )

        url = reverse("inquiries:inquiry-list-create")

        # Sales Agent access
        self.client.force_authenticate(user=self.agent_user)
        res_agent = self.client.get(url)
        self.assertEqual(res_agent.status_code, status.HTTP_200_OK)
        results = res_agent.json()["data"]["results"]
        self.assertEqual(len(results), 2)

        # Filter by status: ?status=IN_CONTACT
        res_filtered = self.client.get(f"{url}?status=IN_CONTACT")
        self.assertEqual(res_filtered.status_code, status.HTTP_200_OK)
        filtered_results = res_filtered.json()["data"]["results"]
        self.assertEqual(len(filtered_results), 1)
        self.assertEqual(filtered_results[0]["inquiry_number"], "INQ-2026-2222")

        # Filter by assigned_agent: ?assigned_agent=me
        res_me = self.client.get(f"{url}?assigned_agent=me")
        self.assertEqual(res_me.status_code, status.HTTP_200_OK)
        me_results = res_me.json()["data"]["results"]
        self.assertEqual(len(me_results), 1)
        self.assertEqual(me_results[0]["inquiry_number"], "INQ-2026-2222")

    def test_inquiry_detail_and_agent_lifecycle_update(self):
        """Sales Agent can retrieve lead details and transition status."""
        inquiry = Inquiry.objects.create(
            inquiry_number="INQ-2026-7777",
            inquiry_type=InquiryType.JOURNEY,
            trip=self.trip,
            full_name="Sir Arthur Conan Doyle",
            email="doyle@sherlock.co.uk",
            status=InquiryStatus.NEW,
        )

        url = reverse("inquiries:inquiry-detail", kwargs={"inquiry_number": inquiry.inquiry_number})

        # As Sales Agent
        self.client.force_authenticate(user=self.agent_user)

        # GET detail
        res_detail = self.client.get(url)
        self.assertEqual(res_detail.status_code, status.HTTP_200_OK)
        self.assertEqual(res_detail.json()["data"]["full_name"], "Sir Arthur Conan Doyle")

        # PATCH update: assign agent and update status to IN_CONTACT
        patch_payload = {
            "status": InquiryStatus.IN_CONTACT,
            "assigned_agent_id": str(self.agent_user.id),
        }
        res_patch = self.client.patch(url, patch_payload, format="json")
        self.assertEqual(res_patch.status_code, status.HTTP_200_OK)
        data = res_patch.json()["data"]

        self.assertEqual(data["status"], InquiryStatus.IN_CONTACT)
        self.assertEqual(data["assigned_agent"]["email"], self.agent_user.email)

        # Verify DB
        inquiry.refresh_from_db()
        self.assertEqual(inquiry.status, InquiryStatus.IN_CONTACT)
        self.assertEqual(inquiry.assigned_agent, self.agent_user)

    def test_inquiry_consultation_notes_thread(self):
        """Agents can add and list internal consultation notes on an inquiry."""
        inquiry = Inquiry.objects.create(
            inquiry_number="INQ-2026-8888",
            inquiry_type=InquiryType.TAILOR_MADE,
            full_name="Lady Hester Stanhope",
            email="hester@travels.org",
            status=InquiryStatus.ASSIGNED,
            assigned_agent=self.agent_user,
        )

        url = reverse("inquiries:inquiry-notes", kwargs={"inquiry_number": inquiry.inquiry_number})

        # Customer is forbidden from viewing or creating notes
        self.client.force_authenticate(user=self.customer_user)
        res_cust = self.client.get(url)
        self.assertEqual(res_cust.status_code, status.HTTP_403_FORBIDDEN)

        # Agent creates note
        self.client.force_authenticate(user=self.agent_user)
        note_payload = {
            "note_text": "Spoke via WhatsApp. Client requested custom tenting at 4200m and oxygen canister backup.",
        }
        res_post = self.client.post(url, note_payload, format="json")
        self.assertEqual(res_post.status_code, status.HTTP_201_CREATED)
        note_data = res_post.json()["data"]
        self.assertEqual(note_data["author"]["email"], self.agent_user.email)

        # GET notes thread
        res_list = self.client.get(url)
        self.assertEqual(res_list.status_code, status.HTTP_200_OK)
        notes = res_list.json()["data"]["results"]
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["note_text"], note_payload["note_text"])
