"""
Revenue is earned when a trek completes (plus manual entries), never when a
lead is merely booked or a deposit arrives.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from apps.bookings.models import Booking
from apps.inquiries.models import Inquiry, InquiryStatus, InquiryType, RevenueEntry
from apps.inquiries.services import advance_travel_statuses, transition_status
from apps.inquiries.services.revenue import revenue_summary
from apps.inquiries.test_assignment import CRMTestBase


class RevenueTestBase(CRMTestBase):
    _counter = 0

    def make_lead(self, status=InquiryStatus.IN_CONTACT, group_size=2, **extra):
        RevenueTestBase._counter += 1
        number = f"INQ-2026-8{RevenueTestBase._counter:03d}"
        return Inquiry.objects.create(**{
            "inquiry_number": number,
            "inquiry_type": InquiryType.JOURNEY,
            "trip": self.trip,
            "departure": self.march_departure,
            "full_name": "Ang Dawa",
            "email": f"{number.lower()}@test.local",
            "status": status,
            "group_size": group_size,
            **extra,
        })

    def complete(self, lead):
        transition_status(lead, InquiryStatus.BOOKED, departure=self.march_departure)
        return transition_status(lead, InquiryStatus.COMPLETED)

    def this_month(self):
        return revenue_summary(6)["totals"]["this_month"]


class CompletionDrivesRevenueTests(RevenueTestBase):
    def test_booked_and_traveling_leads_earn_nothing_yet(self):
        lead = self.make_lead()
        transition_status(lead, InquiryStatus.BOOKED, departure=self.march_departure)
        self.assertEqual(self.this_month(), 0.0)
        transition_status(lead, InquiryStatus.TRAVELING)
        self.assertEqual(self.this_month(), 0.0)

    def test_completing_adds_price_times_travellers_to_this_month(self):
        lead = self.complete(self.make_lead(group_size=3))
        self.assertIsNotNone(lead.completed_at)
        self.assertEqual(lead.revenue_usd, Decimal("4500.00"))

        summary = revenue_summary(6)
        self.assertEqual(summary["totals"]["this_month"], 4500.0)
        self.assertEqual(summary["totals"]["completed_trips"], 1)
        self.assertEqual(summary["totals"]["travelers_completed"], 3)
        self.assertEqual(summary["totals"]["avg_trip_value"], 4500.0)
        self.assertEqual(summary["monthly"][-1]["completed_revenue"], 4500.0)
        self.assertEqual(summary["monthly"][-1]["completed_trips"], 1)

    def test_reopening_a_completed_trip_takes_its_revenue_back_out(self):
        lead = self.complete(self.make_lead())
        lead = transition_status(lead, InquiryStatus.TRAVELING)
        self.assertIsNone(lead.completed_at)
        self.assertIsNone(lead.revenue_usd)
        self.assertEqual(self.this_month(), 0.0)

    def test_nightly_sweep_counts_revenue_once_the_trip_ends(self):
        lead = self.make_lead(group_size=2)
        transition_status(lead, InquiryStatus.BOOKED, departure=self.march_departure)
        advance_travel_statuses(today=self.march_departure.end_date + timedelta(days=1))
        lead.refresh_from_db()
        self.assertEqual(lead.status, InquiryStatus.COMPLETED)
        self.assertEqual(self.this_month(), 3000.0)

    def test_deposits_and_bookings_are_not_revenue(self):
        Booking.objects.create(
            booking_reference="DS-2026-REV1",
            customer_name="Paid Up",
            customer_email="paid@example.com",
            departure=self.march_departure,
            num_travelers=2,
            total_amount_usd=Decimal("3000.00"),
            deposit_amount_usd=Decimal("600.00"),
            balance_amount_usd=Decimal("2400.00"),
            amount_paid_usd=Decimal("3000.00"),
            status="FULLY_PAID",
            trip_start_date=self.start_date,
        )
        summary = revenue_summary(6)
        self.assertEqual(summary["totals"]["all_time"], 0.0)
        # ...but the website booking does show up as a new booking.
        self.assertEqual(summary["monthly"][-1]["new_bookings"], 1)


class RevenueSummaryShapeTests(RevenueTestBase):
    def test_every_month_is_present_even_when_empty(self):
        summary = revenue_summary(12, today=date(2026, 3, 15))
        self.assertEqual([row["month"] for row in summary["monthly"]][:3], ["2025-04", "2025-05", "2025-06"])
        self.assertEqual(summary["monthly"][-1]["month"], "2026-03")
        self.assertTrue(all(row["revenue"] == 0.0 for row in summary["monthly"]))

    def test_growth_is_null_without_last_months_revenue(self):
        self.complete(self.make_lead())
        self.assertIsNone(revenue_summary(6)["totals"]["mom_growth_percent"])

    def test_growth_compares_with_last_month(self):
        today = timezone.localdate()
        last_month = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
        RevenueEntry.objects.create(amount_usd=Decimal("1000.00"), earned_on=last_month, description="Last month")
        RevenueEntry.objects.create(amount_usd=Decimal("1500.00"), earned_on=today, description="This month")
        self.assertEqual(revenue_summary(6)["totals"]["mom_growth_percent"], 50.0)

    def test_destinations_split_completed_and_manual_revenue(self):
        self.complete(self.make_lead(group_size=1))  # 1500 on Annapurna
        RevenueEntry.objects.create(amount_usd=Decimal("500.00"), description="Airport pickup")
        by_destination = revenue_summary(6)["by_destination"]
        self.assertEqual([(row["name"], row["revenue"]) for row in by_destination], [("Annapurna", 1500.0), ("Other / unassigned", 500.0)])
        self.assertAlmostEqual(sum(row["share_percent"] for row in by_destination), 100.0, places=0)

    def test_top_treks_and_recent_events(self):
        self.complete(self.make_lead(group_size=2))
        RevenueEntry.objects.create(amount_usd=Decimal("250.00"), description="Porter tip pool", trip=self.trip)
        summary = revenue_summary(6)
        self.assertEqual(summary["by_trek"][0]["slug"], "annapurna-circuit")
        self.assertEqual(summary["by_trek"][0]["revenue"], 3250.0)
        self.assertEqual({event["source"] for event in summary["recent"]}, {"TREK_COMPLETED", "MANUAL"})


class RevenueEndpointTests(RevenueTestBase):
    url = reverse("inquiries:crm-revenue")
    entries_url = reverse("inquiries:crm-revenue-entries")

    def test_staff_can_read_revenue_and_months_is_validated(self):
        self.client.force_authenticate(self.annapurna_agent)
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_200_OK)
        self.assertEqual(len(self.client.get(self.url, {"months": "12"}).json()["data"]["monthly"]), 12)
        self.assertEqual(self.client.get(self.url, {"months": "7"}).status_code, status.HTTP_400_BAD_REQUEST)

        self.client.force_authenticate(self.customer)
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_403_FORBIDDEN)

    def test_only_admins_can_add_or_remove_manual_revenue(self):
        payload = {"amount_usd": "750.00", "description": "Private jeep safari", "trip_id": str(self.trip.id)}

        self.client.force_authenticate(self.annapurna_agent)
        self.assertEqual(self.client.post(self.entries_url, payload, format="json").status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.get(self.entries_url).status_code, status.HTTP_200_OK)

        self.client.force_authenticate(self.admin)
        created = self.client.post(self.entries_url, payload, format="json")
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        entry = created.json()["data"]
        self.assertEqual(entry["trip_title"], "Annapurna Circuit")
        self.assertEqual(entry["earned_on"], timezone.localdate().isoformat())
        self.assertEqual(self.this_month(), 750.0)

        detail = reverse("inquiries:crm-revenue-entry-detail", kwargs={"pk": entry["id"]})
        self.client.force_authenticate(self.annapurna_agent)
        self.assertEqual(self.client.delete(detail).status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.delete(detail).status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(self.this_month(), 0.0)

    def test_manual_revenue_must_be_positive_and_described(self):
        self.client.force_authenticate(self.admin)
        for payload in ({"amount_usd": "0", "description": "x"}, {"amount_usd": "-5", "description": "x"}, {"amount_usd": "10", "description": "   "}):
            with self.subTest(payload=payload):
                self.assertEqual(self.client.post(self.entries_url, payload, format="json").status_code, status.HTTP_400_BAD_REQUEST)

    def test_dashboard_card_matches_the_revenue_page(self):
        self.complete(self.make_lead(group_size=2))
        RevenueEntry.objects.create(amount_usd=Decimal("400.00"), description="Extra")
        self.client.force_authenticate(self.admin)
        dashboard = self.client.get(reverse("dashboard-analytics")).json()["data"]
        revenue = self.client.get(self.url).json()["data"]
        self.assertEqual(dashboard["metrics"]["monthly_revenue"], revenue["totals"]["this_month"])
        self.assertEqual(dashboard["metrics"]["total_revenue"], revenue["totals"]["all_time"])
        self.assertEqual([row["revenue"] for row in dashboard["monthly_trends"]], [row["revenue"] for row in revenue["monthly"]])
