"""
Tour-based lead filtering, routing rules, and bulk reassignment.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import UserRole
from apps.destinations.models import ActivityCategory, Destination
from apps.inquiries.models import (
    Activity,
    ActivityChannel,
    Inquiry,
    InquiryStatus,
    InquiryType,
    LeadAssignmentRule,
)
from apps.trips.models import Trip, TripDeparture

User = get_user_model()


class CRMTestBase(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="crm-admin@test.local",
            password="StrongTestPass123!",
            role=UserRole.ADMIN,
            is_staff=True,
        )
        self.annapurna_agent = User.objects.create_user(
            email="annapurna.agent@test.local",
            password="StrongTestPass123!",
            role=UserRole.SALES_AGENT,
            first_name="Anu",
            last_name="Gurung",
        )
        self.other_agent = User.objects.create_user(
            email="other.agent@test.local",
            password="StrongTestPass123!",
            role=UserRole.SALES_AGENT,
        )
        self.customer = User.objects.create_user(
            email="customer@test.local", password="StrongTestPass123!"
        )

        self.destination = Destination.objects.create(
            name="Annapurna", slug="annapurna", country="NEPAL"
        )
        self.category = ActivityCategory.objects.create(name="Treks", slug="treks")
        self.trip = Trip.objects.create(
            destination=self.destination,
            category=self.category,
            title="Annapurna Circuit",
            slug="annapurna-circuit",
            duration_days=16,
            difficulty_grade="DIFFICULT",
            starting_price_usd=Decimal("1500.00"),
            overview="Annapurna circuit trek",
        )
        self.other_trip = Trip.objects.create(
            destination=self.destination,
            category=self.category,
            title="Everest Base Camp",
            slug="everest-base-camp",
            duration_days=14,
            difficulty_grade="DIFFICULT",
            starting_price_usd=Decimal("1800.00"),
            overview="EBC trek",
        )
        self.start_date = date.today() + timedelta(days=60)
        self.march_departure = TripDeparture.objects.create(
            trip=self.trip,
            start_date=self.start_date,
            end_date=self.start_date + timedelta(days=16),
            price_usd=Decimal("1500.00"),
            max_seats=10,
        )

    def submit_inquiry(self, **overrides):
        payload = {
            "inquiry_type": InquiryType.JOURNEY,
            "full_name": "Prospective Trekker",
            "email": "prospect@example.com",
            "message": "Interested in this departure.",
            "trip": str(self.trip.id),
            "departure": str(self.march_departure.id),
        }
        payload.update(overrides)
        return self.client.post(
            reverse("inquiries:inquiry-list-create"), payload, format="json"
        )


class InquiryFilterTests(CRMTestBase):
    def setUp(self):
        super().setUp()
        self.matching = Inquiry.objects.create(
            inquiry_number="INQ-2026-0001",
            inquiry_type=InquiryType.JOURNEY,
            trip=self.trip,
            departure=self.march_departure,
            full_name="Wants Annapurna",
            email="wants@example.com",
        )
        self.unrelated = Inquiry.objects.create(
            inquiry_number="INQ-2026-0002",
            inquiry_type=InquiryType.JOURNEY,
            trip=self.other_trip,
            full_name="Wants Everest",
            email="everest@example.com",
        )
        self.client.force_authenticate(user=self.admin)

    def test_filter_by_departure(self):
        response = self.client.get(
            reverse("inquiries:inquiry-list-create"),
            {"departure": str(self.march_departure.id)},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json()["data"]["results"]
        self.assertEqual([r["inquiry_number"] for r in results], ["INQ-2026-0001"])

    def test_filter_by_trip_slug(self):
        response = self.client.get(
            reverse("inquiries:inquiry-list-create"), {"trip": "everest-base-camp"}
        )
        results = response.json()["data"]["results"]
        self.assertEqual([r["inquiry_number"] for r in results], ["INQ-2026-0002"])

    def test_malformed_agent_filter_returns_400_not_500(self):
        response = self.client.get(
            reverse("inquiries:inquiry-list-create"), {"assigned_agent": "not-a-uuid"}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unassigned_sentinel(self):
        self.matching.assigned_agent = self.annapurna_agent
        self.matching.save()
        response = self.client.get(
            reverse("inquiries:inquiry-list-create"), {"assigned_agent": "unassigned"}
        )
        results = response.json()["data"]["results"]
        self.assertEqual([r["inquiry_number"] for r in results], ["INQ-2026-0002"])

    def test_list_exposes_trip_and_departure_labels(self):
        response = self.client.get(
            reverse("inquiries:inquiry-list-create"),
            {"departure": str(self.march_departure.id)},
        )
        row = response.json()["data"]["results"][0]
        self.assertEqual(row["trip_title"], "Annapurna Circuit")
        self.assertIsNotNone(row["departure_label"])


class AssignmentRuleTests(CRMTestBase):
    def test_new_leads_stay_new_and_unassigned_even_when_a_rule_matches(self):
        # Agent routing was retired from the CRM: rules no longer act on intake.
        LeadAssignmentRule.objects.create(
            departure=self.march_departure, agent=self.annapurna_agent
        )
        response = self.submit_inquiry()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        inquiry = Inquiry.objects.get(email="prospect@example.com")
        self.assertIsNone(inquiry.assigned_agent)
        self.assertEqual(inquiry.status, InquiryStatus.NEW)
        self.assertFalse(Activity.objects.filter(inquiry=inquiry, channel=ActivityChannel.SYSTEM).exists())

    def test_rule_crud_requires_admin(self):
        url = reverse("inquiries:crm-assignment-rules")
        self.client.force_authenticate(user=self.annapurna_agent)
        self.assertEqual(
            self.client.get(url).status_code, status.HTTP_403_FORBIDDEN
        )

    def test_rule_rejects_overlapping_targets(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            reverse("inquiries:crm-assignment-rules"),
            {
                "departure": str(self.march_departure.id),
                "trip": str(self.trip.id),
                "agent_id": str(self.annapurna_agent.id),
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rule_rejects_a_non_staff_agent(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            reverse("inquiries:crm-assignment-rules"),
            {"trip": str(self.trip.id), "agent_id": str(self.customer.id)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class BulkAssignTests(CRMTestBase):
    def setUp(self):
        super().setUp()
        self.leads = [
            Inquiry.objects.create(
                inquiry_number=f"INQ-2026-10{i}",
                inquiry_type=InquiryType.JOURNEY,
                trip=self.trip,
                departure=self.march_departure,
                full_name=f"Lead {i}",
                email=f"lead{i}@example.com",
            )
            for i in range(3)
        ]
        self.closed_lead = Inquiry.objects.create(
            inquiry_number="INQ-2026-1099",
            inquiry_type=InquiryType.JOURNEY,
            trip=self.trip,
            departure=self.march_departure,
            full_name="Closed Lead",
            email="closed@example.com",
            status=InquiryStatus.CLOSED,
        )

    def test_assign_a_whole_departure_to_a_specialist(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            reverse("inquiries:crm-bulk-assign"),
            {
                "departure": str(self.march_departure.id),
                "agent_id": str(self.annapurna_agent.id),
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["data"]["reassigned"], 3)

        for lead in self.leads:
            lead.refresh_from_db()
            self.assertEqual(lead.assigned_agent, self.annapurna_agent)
            self.assertEqual(lead.status, InquiryStatus.ASSIGNED)

        # Closed leads are left alone unless explicitly included.
        self.closed_lead.refresh_from_db()
        self.assertIsNone(self.closed_lead.assigned_agent)

    def test_each_reassignment_is_recorded_on_the_timeline(self):
        self.client.force_authenticate(user=self.admin)
        self.client.post(
            reverse("inquiries:crm-bulk-assign"),
            {"trip": "annapurna-circuit", "agent_id": str(self.annapurna_agent.id)},
            format="json",
        )
        for lead in self.leads:
            activity = Activity.objects.get(inquiry=lead, channel=ActivityChannel.SYSTEM)
            self.assertEqual(activity.metadata["reason"], "bulk_assign")

    def test_reassigning_to_the_current_owner_is_a_no_op(self):
        for lead in self.leads:
            lead.assigned_agent = self.annapurna_agent
            lead.save()

        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            reverse("inquiries:crm-bulk-assign"),
            {
                "departure": str(self.march_departure.id),
                "agent_id": str(self.annapurna_agent.id),
            },
            format="json",
        )
        self.assertEqual(response.json()["data"]["reassigned"], 0)
        self.assertEqual(Activity.objects.filter(channel=ActivityChannel.SYSTEM).count(), 0)

    def test_bulk_assign_requires_admin(self):
        self.client.force_authenticate(user=self.annapurna_agent)
        response = self.client.post(
            reverse("inquiries:crm-bulk-assign"),
            {"departure": str(self.march_departure.id), "agent_id": str(self.other_agent.id)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_bulk_assign_needs_a_selector(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            reverse("inquiries:crm-bulk-assign"),
            {"agent_id": str(self.annapurna_agent.id)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class LeadsByDepartureBoardTests(CRMTestBase):
    def test_board_counts_open_leads_against_seats(self):
        for i in range(4):
            Inquiry.objects.create(
                inquiry_number=f"INQ-2026-20{i}",
                inquiry_type=InquiryType.JOURNEY,
                trip=self.trip,
                departure=self.march_departure,
                full_name=f"Lead {i}",
                email=f"board{i}@example.com",
            )
        self.march_departure.booked_seats = 8
        self.march_departure.save()

        self.client.force_authenticate(user=self.annapurna_agent)
        response = self.client.get(reverse("inquiries:crm-leads-by-departure"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        row = response.json()["data"]["results"][0]
        self.assertEqual(row["open_inquiry_count"], 4)
        self.assertEqual(row["booked_seats"], 8)
        # 4 open leads + 8 booked exceeds 10 seats.
        self.assertEqual(row["capacity_state"], "OVERSUBSCRIBED")

    def test_board_is_closed_to_customers(self):
        self.client.force_authenticate(user=self.customer)
        response = self.client.get(reverse("inquiries:crm-leads-by-departure"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class AgentListTests(CRMTestBase):
    def test_agents_are_listable_by_a_sales_agent(self):
        self.client.force_authenticate(user=self.annapurna_agent)
        response = self.client.get(reverse("users:agent-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        emails = {row["email"] for row in response.json()["data"]}
        self.assertIn(self.annapurna_agent.email, emails)
        self.assertIn(self.admin.email, emails)
        self.assertNotIn(self.customer.email, emails)

    def test_customers_cannot_list_agents(self):
        self.client.force_authenticate(user=self.customer)
        response = self.client.get(reverse("users:agent-list"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
