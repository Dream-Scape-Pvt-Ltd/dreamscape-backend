"""
The booked -> traveling -> completed stretch of the CRM pipeline: seats on the
departure, date-driven status moves, and per-trek revenue.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import UserRole
from apps.destinations.models import ActivityCategory, Destination
from apps.inquiries.models import Inquiry, InquiryStatus, InquiryType
from apps.inquiries.services import advance_travel_statuses
from apps.trips.models import Trip, TripDeparture

User = get_user_model()


class TravelLifecycleTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="travel-admin@test.local",
            password="StrongTestPass123!",
            role=UserRole.ADMIN,
            is_staff=True,
        )
        destination = Destination.objects.create(name="Everest", slug="everest", country="NEPAL")
        category = ActivityCategory.objects.create(name="Treks", slug="treks")
        self.trip = Trip.objects.create(
            destination=destination,
            category=category,
            title="Everest Base Camp",
            slug="everest-base-camp",
            duration_days=14,
            difficulty_grade="GRADE_3",
            starting_price_usd=Decimal("1500"),
            overview="Everest trekking",
        )
        self.departure = TripDeparture.objects.create(
            trip=self.trip,
            start_date=date.today() + timedelta(days=30),
            end_date=date.today() + timedelta(days=44),
            price_usd=Decimal("1500"),
            max_seats=10,
        )
        self.client.force_authenticate(self.admin)

    def make_lead(self, number="INQ-2026-0001", **extra):
        defaults = {
            "inquiry_number": number,
            "inquiry_type": InquiryType.JOURNEY,
            "trip": self.trip,
            "full_name": "Pemba Sherpa",
            "email": f"{number.lower()}@test.local",
            "status": InquiryStatus.IN_CONTACT,
            "group_size": 3,
        }
        defaults.update(extra)
        return Inquiry.objects.create(**defaults)

    def patch(self, inquiry, **body):
        url = reverse("inquiries:inquiry-detail", kwargs={"inquiry_number": inquiry.inquiry_number})
        return self.client.patch(url, body, format="json")

    def test_booking_a_lead_takes_seats_on_its_departure(self):
        lead = self.make_lead()

        response = self.patch(lead, status="BOOKED", departure_id=str(self.departure.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.departure.refresh_from_db()
        lead.refresh_from_db()
        self.assertEqual(self.departure.booked_seats, 3)
        self.assertEqual(lead.seats_held, 3)
        self.assertEqual(lead.departure_id, self.departure.id)

    def test_travelers_count_overrides_group_size(self):
        lead = self.make_lead(departure=self.departure)

        self.patch(lead, status="BOOKED", travelers_count=5)

        self.departure.refresh_from_db()
        self.assertEqual(self.departure.booked_seats, 5)

    def test_booking_requires_a_departure(self):
        lead = self.make_lead()

        response = self.patch(lead, status="BOOKED")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        lead.refresh_from_db()
        self.assertEqual(lead.status, InquiryStatus.IN_CONTACT)

    def test_booking_more_people_than_seats_left_is_refused(self):
        lead = self.make_lead(departure=self.departure, group_size=11)

        response = self.patch(lead, status="BOOKED")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.departure.refresh_from_db()
        self.assertEqual(self.departure.booked_seats, 0)

    def test_closing_a_booked_lead_gives_its_seats_back(self):
        lead = self.make_lead(departure=self.departure)
        self.patch(lead, status="BOOKED")

        response = self.patch(lead, status="CLOSED", lost_reason="DATES")

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.departure.refresh_from_db()
        lead.refresh_from_db()
        self.assertEqual(self.departure.booked_seats, 0)
        self.assertEqual(lead.seats_held, 0)

    def test_departure_start_moves_booked_leads_to_traveling(self):
        lead = self.make_lead(departure=self.departure)
        self.patch(lead, status="BOOKED")

        advance_travel_statuses(today=self.departure.start_date)

        lead.refresh_from_db()
        self.assertEqual(lead.status, InquiryStatus.TRAVELING)

    def test_passing_end_date_completes_the_trip_and_records_revenue(self):
        lead = self.make_lead(departure=self.departure)
        self.patch(lead, status="BOOKED")

        advance_travel_statuses(today=self.departure.start_date)
        advance_travel_statuses(today=self.departure.end_date + timedelta(days=1))

        lead.refresh_from_db()
        self.departure.refresh_from_db()
        self.assertEqual(lead.status, InquiryStatus.COMPLETED)
        self.assertEqual(lead.revenue_usd, Decimal("4500.00"))
        # Travellers keep their seats once the trip has happened.
        self.assertEqual(self.departure.booked_seats, 3)

    def test_leads_before_their_departure_are_left_alone(self):
        lead = self.make_lead(departure=self.departure)
        self.patch(lead, status="BOOKED")

        advance_travel_statuses(today=self.departure.start_date - timedelta(days=1))

        lead.refresh_from_db()
        self.assertEqual(lead.status, InquiryStatus.BOOKED)

    def test_trek_pipeline_reports_counts_and_completed_revenue(self):
        first = self.make_lead("INQ-2026-0001", departure=self.departure)
        second = self.make_lead("INQ-2026-0002", departure=self.departure, group_size=2)
        self.make_lead("INQ-2026-0003", status=InquiryStatus.NEW)
        self.patch(first, status="BOOKED")
        self.patch(second, status="BOOKED")
        advance_travel_statuses(today=self.departure.end_date + timedelta(days=1))

        response = self.client.get(reverse("inquiries:crm-trek-pipeline"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data.get("data", response.data)
        row = next(item for item in data["results"] if item["slug"] == self.trip.slug)
        self.assertEqual(row["by_status"]["COMPLETED"], 2)
        self.assertEqual(row["by_status"]["NEW"], 1)
        self.assertEqual(row["travelers_completed"], 5)
        self.assertEqual(Decimal(row["revenue_usd"]), Decimal("7500.00"))
