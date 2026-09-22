"""
Seat ledger, capacity board, and waitlist behaviour.

The regression that matters most here is concurrency: the booking flow must
still hold a row lock over the seat counter now that `available_seats` is
derived rather than stored.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import UserRole
from apps.bookings.models import DepartureWaitlistEntry, WaitlistStatus
from apps.bookings.services import join_waitlist, promote_waitlist
from apps.destinations.models import ActivityCategory, Destination
from apps.trips.models import DepartureStatus, Trip, TripDeparture

User = get_user_model()


class CapacityTestBase(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="capacity-admin@test.local",
            password="StrongTestPass123!",
            role=UserRole.ADMIN,
            is_staff=True,
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
            difficulty_grade="GRADE_3",
            starting_price_usd=Decimal("1500.00"),
            overview="Annapurna circuit trek",
        )
        self.start_date = date.today() + timedelta(days=60)
        self.departure = TripDeparture.objects.create(
            trip=self.trip,
            start_date=self.start_date,
            end_date=self.start_date + timedelta(days=16),
            price_usd=Decimal("1500.00"),
            max_seats=10,
        )


class SeatLedgerTests(CapacityTestBase):
    def test_available_seats_accounts_for_reserved_and_booked(self):
        self.departure.booked_seats = 4
        self.departure.reserved_seats = 2
        self.departure.save()
        self.assertEqual(self.departure.available_seats, 4)

    def test_recompute_status_flips_to_waitlist_when_full(self):
        self.departure.booked_seats = 10
        self.assertTrue(self.departure.recompute_status())
        self.assertEqual(self.departure.status, DepartureStatus.WAITLIST)

    def test_recompute_status_sold_out_when_waitlist_disabled(self):
        self.departure.waitlist_enabled = False
        self.departure.booked_seats = 10
        self.departure.recompute_status()
        self.assertEqual(self.departure.status, DepartureStatus.SOLD_OUT)

    def test_recompute_status_reports_few_seats_left(self):
        self.departure.booked_seats = 8  # 2 left, threshold is 3
        self.departure.recompute_status()
        self.assertEqual(self.departure.status, DepartureStatus.LIMITED)
        self.assertEqual(self.departure.availability_state, "FEW_SEATS_LEFT")

    def test_status_locked_pins_the_admin_choice(self):
        """An admin who forces SOLD_OUT must not have it drift back."""
        self.departure.status = DepartureStatus.SOLD_OUT
        self.departure.status_locked = True
        self.assertFalse(self.departure.recompute_status())
        self.assertEqual(self.departure.status, DepartureStatus.SOLD_OUT)

    def test_reserving_seats_beyond_bookings_is_rejected(self):
        self.departure.booked_seats = 8
        self.departure.save()

        url = reverse(
            "trips:departure-detail",
            kwargs={"slug": self.trip.slug, "departure_id": self.departure.id},
        )
        self.client.force_authenticate(user=self.admin)
        response = self.client.patch(url, {"reserved_seats": 5}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_db_constraint_blocks_overbooking(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                TripDeparture.objects.create(
                    trip=self.trip,
                    start_date=self.start_date,
                    end_date=self.start_date + timedelta(days=5),
                    price_usd=Decimal("100.00"),
                    max_seats=5,
                    booked_seats=6,
                )


class PublicDepartureContractTests(CapacityTestBase):
    def test_public_response_still_exposes_available_seats(self):
        """The column is gone; the API field must not be."""
        url = reverse("trips:departure-list", kwargs={"slug": self.trip.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        row = response.json()["data"]["results"][0]
        self.assertEqual(row["available_seats"], 10)
        self.assertEqual(row["availability_state"], "AVAILABLE")

    def test_available_only_filter_excludes_full_departures(self):
        self.departure.booked_seats = 10
        self.departure.recompute_status()
        self.departure.save()

        url = reverse("trips:departure-list", kwargs={"slug": self.trip.slug})
        response = self.client.get(url, {"available_only": "true"})
        self.assertEqual(response.json()["data"]["results"], [])


class CapacityBoardTests(CapacityTestBase):
    def test_board_requires_admin(self):
        url = reverse("trips:departure-capacity-board")
        self.assertIn(
            self.client.get(url).status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )

    def test_board_reports_counts_and_capacity_state(self):
        self.departure.booked_seats = 9
        self.departure.save()

        self.client.force_authenticate(user=self.admin)
        response = self.client.get(reverse("trips:departure-capacity-board"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        row = response.json()["data"]["results"][0]
        self.assertEqual(row["booked_seats"], 9)
        self.assertEqual(row["available_seats"], 1)
        self.assertEqual(row["utilization_pct"], 90)
        self.assertEqual(row["capacity_state"], "NEARLY_FULL")
        self.assertEqual(row["open_inquiry_count"], 0)
        self.assertEqual(row["waitlisted_count"], 0)

    def test_capacity_state_filter_matches_the_serializer(self):
        self.departure.booked_seats = 9
        self.departure.save()

        self.client.force_authenticate(user=self.admin)
        url = reverse("trips:departure-capacity-board")

        nearly = self.client.get(url, {"capacity_state": "NEARLY_FULL"}).json()
        self.assertEqual(len(nearly["data"]["results"]), 1)

        healthy = self.client.get(url, {"capacity_state": "HEALTHY"}).json()
        self.assertEqual(healthy["data"]["results"], [])


class WaitlistTests(CapacityTestBase):
    def _fill(self):
        self.departure.booked_seats = self.departure.max_seats
        self.departure.recompute_status()
        self.departure.save()

    def test_join_waitlist_assigns_sequential_positions(self):
        self._fill()
        url = reverse("bookings:waitlist-join")

        first = self.client.post(
            url,
            {
                "departure_id": str(self.departure.id),
                "customer_name": "First Hiker",
                "customer_email": "first@example.com",
                "num_travelers": 1,
            },
            format="json",
        )
        second = self.client.post(
            url,
            {
                "departure_id": str(self.departure.id),
                "customer_name": "Second Hiker",
                "customer_email": "second@example.com",
                "num_travelers": 1,
            },
            format="json",
        )
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(first.json()["data"]["position"], 1)
        self.assertEqual(second.json()["data"]["position"], 2)

    def test_rejoining_returns_the_same_entry(self):
        """A double form submission must not create a second queue slot."""
        self._fill()
        url = reverse("bookings:waitlist-join")
        payload = {
            "departure_id": str(self.departure.id),
            "customer_name": "Repeat Hiker",
            "customer_email": "repeat@example.com",
            "num_travelers": 1,
        }
        first = self.client.post(url, payload, format="json").json()
        second = self.client.post(url, payload, format="json").json()
        self.assertEqual(first["data"]["id"], second["data"]["id"])
        self.assertEqual(DepartureWaitlistEntry.objects.count(), 1)

    def test_join_rejected_when_waitlist_disabled(self):
        self.departure.waitlist_enabled = False
        self._fill()

        response = self.client.post(
            reverse("bookings:waitlist-join"),
            {
                "departure_id": str(self.departure.id),
                "customer_name": "Turned Away",
                "customer_email": "away@example.com",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_promotion_offers_the_head_of_the_queue(self):
        self._fill()
        head = join_waitlist(
            self.departure,
            customer_name="Head",
            customer_email="head@example.com",
            num_travelers=1,
        )
        join_waitlist(
            self.departure,
            customer_name="Tail",
            customer_email="tail@example.com",
            num_travelers=1,
        )

        # A cancellation frees one seat.
        self.departure.booked_seats -= 1
        self.departure.save()

        promoted = promote_waitlist(self.departure)
        self.assertEqual([e.id for e in promoted], [head.id])

        head.refresh_from_db()
        self.assertEqual(head.status, WaitlistStatus.OFFERED)
        self.assertIsNotNone(head.offer_expires_at)

    def test_promotion_skips_a_party_too_large_for_the_free_seats(self):
        self._fill()
        big_party = join_waitlist(
            self.departure,
            customer_name="Group of Four",
            customer_email="four@example.com",
            num_travelers=4,
        )
        solo = join_waitlist(
            self.departure,
            customer_name="Solo",
            customer_email="solo@example.com",
            num_travelers=1,
        )

        self.departure.booked_seats -= 1  # one seat frees up
        self.departure.save()

        promoted = promote_waitlist(self.departure)
        self.assertEqual([e.id for e in promoted], [solo.id])

        big_party.refresh_from_db()
        self.assertEqual(big_party.status, WaitlistStatus.WAITING)


class CancellationPromotesWaitlistTests(CapacityTestBase):
    def test_cancelling_a_booking_offers_the_seat_onwards(self):
        from apps.bookings.models import Booking, BookingStatus

        self.departure.booked_seats = 10
        self.departure.recompute_status()
        self.departure.save()

        booking = Booking.objects.create(
            booking_reference="DS-2026-WAIT01",
            customer_name="Leaving Traveller",
            customer_email="leaving@example.com",
            departure=self.departure,
            num_travelers=1,
            total_amount_usd=Decimal("1500.00"),
            deposit_amount_usd=Decimal("300.00"),
            balance_amount_usd=Decimal("1200.00"),
            trip_start_date=self.start_date,
            status=BookingStatus.PENDING,
        )
        entry = join_waitlist(
            self.departure,
            customer_name="Next Up",
            customer_email="nextup@example.com",
            num_travelers=1,
        )

        self.client.force_authenticate(user=self.admin)
        url = reverse(
            "bookings:booking-cancel",
            kwargs={"booking_reference": booking.booking_reference},
        )
        response = self.client.patch(url, {"cancellation_reason": "Plans changed."}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        entry.refresh_from_db()
        self.assertEqual(entry.status, WaitlistStatus.OFFERED)

        self.departure.refresh_from_db()
        self.assertEqual(self.departure.booked_seats, 9)
