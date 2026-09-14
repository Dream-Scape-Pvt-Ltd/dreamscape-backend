import re
from datetime import date, timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import UserRole
from apps.bookings.models import Booking, BookingStatus, PassengerDetail, PaymentType
from apps.destinations.models import Destination, ActivityCategory, DestinationCountry
from apps.trips.models import DifficultyGrade, DepartureStatus, Trip, TripDeparture

User = get_user_model()


class BookingAPITests(APITestCase):
    def setUp(self):
        # Create users
        self.admin_user = User.objects.create_user(
            email="admin@dreamscapetreks.com",
            password="AdminPassword123!",
            first_name="Admin",
            last_name="User",
            role=UserRole.ADMIN,
            is_staff=True,
        )
        self.customer_user = User.objects.create_user(
            email="traveler@example.com",
            password="TravelerPass123!",
            first_name="John",
            last_name="Doe",
            role=UserRole.CUSTOMER,
        )
        self.other_customer = User.objects.create_user(
            email="other@example.com",
            password="OtherPass123!",
            first_name="Jane",
            last_name="Smith",
            role=UserRole.CUSTOMER,
        )

        # Create destination, category, trip, and departure
        self.destination = Destination.objects.create(
            name="Nepal",
            slug="nepal",
            country=DestinationCountry.NEPAL,
        )
        self.category = ActivityCategory.objects.create(
            name="Classic Treks",
            slug="classic-treks",
        )
        self.trip = Trip.objects.create(
            destination=self.destination,
            category=self.category,
            title="Everest Base Camp Trek",
            slug="everest-base-camp-trek",
            duration_days=14,
            altitude_max_meters=5364,
            difficulty_grade=DifficultyGrade.GRADE_4,
            starting_price_usd=Decimal("1500.00"),
            overview="Iconic trek to EBC",
        )

        self.start_date = date.today() + timedelta(days=60)
        self.end_date = self.start_date + timedelta(days=14)
        self.departure = TripDeparture.objects.create(
            trip=self.trip,
            start_date=self.start_date,
            end_date=self.end_date,
            price_usd=Decimal("1500.00"),
            max_seats=10,
            available_seats=10,
            status=DepartureStatus.LIMITED,
        )

        self.valid_passport_expiry = self.start_date + timedelta(days=200)
        self.invalid_passport_expiry = self.start_date + timedelta(days=100)  # Less than 180 days

        self.passenger_payload_1 = {
            "full_name": "John Doe",
            "gender": "Male",
            "date_of_birth": "1990-05-15",
            "passport_number": "PA1234567",
            "passport_expiry_date": str(self.valid_passport_expiry),
            "nationality": "American",
            "insurance_provider": "World Nomads",
            "insurance_policy_number": "WN-998877",
            "insurance_emergency_phone": "+1-800-555-0199",
            "dietary_requirements": "Vegetarian",
            "medical_conditions": "None",
        }

    def test_guest_booking_create_deposit_20_success(self):
        """Guest booking creates booking with 20% deposit and decrements departure seats."""
        url = reverse("bookings:booking-list-create")
        payload = {
            "departure_id": str(self.departure.id),
            "customer_name": "Guest Traveler",
            "customer_email": "guest@example.com",
            "customer_phone": "+1234567890",
            "payment_type": PaymentType.DEPOSIT_20,
            "passengers": [self.passenger_payload_1],
        }

        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        res_json = response.json()
        self.assertTrue(res_json["success"])

        data = res_json["data"]
        self.assertRegex(data["booking_reference"], r"^DS-\d{4}-[A-Z0-9]{5}$")
        self.assertEqual(Decimal(str(data["total_amount_usd"])), Decimal("1500.00"))
        self.assertEqual(Decimal(str(data["deposit_amount_usd"])), Decimal("300.00"))
        self.assertEqual(Decimal(str(data["balance_amount_usd"])), Decimal("1200.00"))
        self.assertEqual(Decimal(str(data["amount_paid_usd"])), Decimal("0.00"))
        self.assertEqual(data["status"], BookingStatus.PENDING)

        expected_due_date = self.start_date - timedelta(days=7)
        self.assertEqual(data["balance_due_date"], str(expected_due_date))

        # Check departure available_seats decremented
        self.departure.refresh_from_db()
        self.assertEqual(self.departure.available_seats, 9)

        # Check passenger created
        passengers = data["passengers"]
        self.assertEqual(len(passengers), 1)
        self.assertEqual(passengers[0]["full_name"], "John Doe")

    def test_authenticated_booking_create_full_100_success(self):
        """Authenticated customer booking with FULL_100 links user and sets full deposit."""
        self.client.force_authenticate(user=self.customer_user)
        url = reverse("bookings:booking-list-create")

        passenger_2 = dict(self.passenger_payload_1)
        passenger_2["full_name"] = "Traveler Two"
        passenger_2["passport_number"] = "PA7654321"

        payload = {
            "departure_id": str(self.departure.id),
            "customer_name": "John Doe",
            "customer_email": self.customer_user.email,
            "customer_phone": "+1234567890",
            "payment_type": PaymentType.FULL_100,
            "passengers": [self.passenger_payload_1, passenger_2],
        }

        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        res_json = response.json()
        data = res_json["data"]

        self.assertEqual(Decimal(str(data["total_amount_usd"])), Decimal("3000.00"))
        self.assertEqual(Decimal(str(data["deposit_amount_usd"])), Decimal("3000.00"))
        self.assertEqual(Decimal(str(data["balance_amount_usd"])), Decimal("0.00"))
        self.assertEqual(data["num_travelers"], 2)

        self.departure.refresh_from_db()
        self.assertEqual(self.departure.available_seats, 8)

        # Verify DB association
        booking = Booking.objects.get(booking_reference=data["booking_reference"])
        self.assertEqual(booking.customer_user, self.customer_user)

    def test_booking_rejection_insufficient_seats(self):
        """Booking fails with 409 SEATS_UNAVAILABLE if departure lacks seats."""
        self.departure.available_seats = 1
        self.departure.save()

        passenger_2 = dict(self.passenger_payload_1)
        passenger_2["full_name"] = "Traveler Two"

        url = reverse("bookings:booking-list-create")
        payload = {
            "departure_id": str(self.departure.id),
            "customer_name": "Too Many Travelers",
            "customer_email": "toomany@example.com",
            "payment_type": PaymentType.DEPOSIT_20,
            "passengers": [self.passenger_payload_1, passenger_2],
        }

        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        res_json = response.json()
        self.assertFalse(res_json["success"])
        self.assertEqual(res_json["error"]["code"], "SEATS_UNAVAILABLE")

        # Seats remain untouched
        self.departure.refresh_from_db()
        self.assertEqual(self.departure.available_seats, 1)

    def test_booking_marks_departure_sold_out_when_seats_reach_zero(self):
        """Departure status transitions to SOLD_OUT when available_seats becomes 0."""
        self.departure.available_seats = 1
        self.departure.save()

        url = reverse("bookings:booking-list-create")
        payload = {
            "departure_id": str(self.departure.id),
            "customer_name": "Last Seat Guest",
            "customer_email": "lastseat@example.com",
            "payment_type": PaymentType.DEPOSIT_20,
            "passengers": [self.passenger_payload_1],
        }

        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.departure.refresh_from_db()
        self.assertEqual(self.departure.available_seats, 0)
        self.assertEqual(self.departure.status, DepartureStatus.SOLD_OUT)

    def test_passenger_passport_expiry_under_six_months_rejected(self):
        """Passenger validation rejects passport expiring in less than 180 days from trip start."""
        url = reverse("bookings:booking-list-create")
        invalid_passenger = dict(self.passenger_payload_1)
        invalid_passenger["passport_expiry_date"] = str(self.invalid_passport_expiry)

        payload = {
            "departure_id": str(self.departure.id),
            "customer_name": "Invalid Passport",
            "customer_email": "invalidpassport@example.com",
            "payment_type": PaymentType.DEPOSIT_20,
            "passengers": [invalid_passenger],
        }

        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        res_json = response.json()
        self.assertFalse(res_json["success"])
        self.assertEqual(res_json["error"]["code"], "VALIDATION_ERROR")

    def test_booking_list_customer_isolation(self):
        """Customer sees only their own bookings; Admin sees all bookings."""
        # Booking for customer_user
        b1 = Booking.objects.create(
            booking_reference="DS-2026-CUST1",
            customer_user=self.customer_user,
            customer_name="John Doe",
            customer_email=self.customer_user.email,
            departure=self.departure,
            num_travelers=1,
            total_amount_usd=Decimal("1500.00"),
            deposit_amount_usd=Decimal("300.00"),
            balance_amount_usd=Decimal("1200.00"),
            trip_start_date=self.start_date,
        )
        # Booking for other_customer
        b2 = Booking.objects.create(
            booking_reference="DS-2026-CUST2",
            customer_user=self.other_customer,
            customer_name="Jane Smith",
            customer_email=self.other_customer.email,
            departure=self.departure,
            num_travelers=1,
            total_amount_usd=Decimal("1500.00"),
            deposit_amount_usd=Decimal("300.00"),
            balance_amount_usd=Decimal("1200.00"),
            trip_start_date=self.start_date,
        )

        url = reverse("bookings:booking-list-create")

        # As customer_user
        self.client.force_authenticate(user=self.customer_user)
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        results = res.json()["data"]["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["booking_reference"], "DS-2026-CUST1")

        # As Admin
        self.client.force_authenticate(user=self.admin_user)
        res_admin = self.client.get(url)
        self.assertEqual(res_admin.status_code, status.HTTP_200_OK)
        admin_results = res_admin.json()["data"]["results"]
        self.assertEqual(len(admin_results), 2)

    def test_booking_detail_permissions(self):
        """Owner and admin can retrieve booking detail; unauthorized customer gets 403."""
        booking = Booking.objects.create(
            booking_reference="DS-2026-DETAIL1",
            customer_user=self.customer_user,
            customer_name="John Doe",
            customer_email=self.customer_user.email,
            departure=self.departure,
            num_travelers=1,
            total_amount_usd=Decimal("1500.00"),
            deposit_amount_usd=Decimal("300.00"),
            balance_amount_usd=Decimal("1200.00"),
            trip_start_date=self.start_date,
        )

        url = reverse("bookings:booking-detail", kwargs={"booking_reference": booking.booking_reference})

        # Owner access -> 200
        self.client.force_authenticate(user=self.customer_user)
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.json()["data"]["booking_reference"], "DS-2026-DETAIL1")

        # Admin access -> 200
        self.client.force_authenticate(user=self.admin_user)
        res_admin = self.client.get(url)
        self.assertEqual(res_admin.status_code, status.HTTP_200_OK)

        # Other customer -> 403 Forbidden
        self.client.force_authenticate(user=self.other_customer)
        res_other = self.client.get(url)
        self.assertEqual(res_other.status_code, status.HTTP_403_FORBIDDEN)

    def test_booking_cancellation_restores_departure_seats(self):
        """Cancelling a booking updates status to CANCELLED and restores seats."""
        # Start with 5 seats
        self.departure.available_seats = 5
        self.departure.save()

        booking = Booking.objects.create(
            booking_reference="DS-2026-CANCEL1",
            customer_user=self.customer_user,
            customer_name="John Doe",
            customer_email=self.customer_user.email,
            departure=self.departure,
            num_travelers=2,
            total_amount_usd=Decimal("3000.00"),
            deposit_amount_usd=Decimal("600.00"),
            balance_amount_usd=Decimal("2400.00"),
            trip_start_date=self.start_date,
            status=BookingStatus.PENDING,
        )

        self.client.force_authenticate(user=self.customer_user)
        url = reverse("bookings:booking-cancel", kwargs={"booking_reference": booking.booking_reference})
        payload = {"cancellation_reason": "Family emergency, unable to travel."}

        response = self.client.patch(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()["data"]

        self.assertEqual(data["status"], BookingStatus.CANCELLED)
        self.assertEqual(data["cancellation_reason"], "Family emergency, unable to travel.")

        # Departure seats restored from 5 to 7
        self.departure.refresh_from_db()
        self.assertEqual(self.departure.available_seats, 7)

        # Attempt to cancel again should fail
        res_again = self.client.patch(url, payload, format="json")
        self.assertEqual(res_again.status_code, status.HTTP_400_BAD_REQUEST)

    def test_passenger_list_and_update(self):
        """Test retrieving passenger list and updating passenger details."""
        booking = Booking.objects.create(
            booking_reference="DS-2026-PASS1",
            customer_user=self.customer_user,
            customer_name="John Doe",
            customer_email=self.customer_user.email,
            departure=self.departure,
            num_travelers=1,
            total_amount_usd=Decimal("1500.00"),
            deposit_amount_usd=Decimal("300.00"),
            balance_amount_usd=Decimal("1200.00"),
            trip_start_date=self.start_date,
        )
        passenger = PassengerDetail.objects.create(
            booking=booking,
            full_name="John Doe",
            date_of_birth="1990-05-15",
            passport_number="PA1234567",
            passport_expiry_date=self.valid_passport_expiry,
            nationality="American",
            insurance_provider="World Nomads",
            insurance_policy_number="WN-112233",
            insurance_emergency_phone="+1-800-555-0199",
            dietary_requirements="None",
        )

        self.client.force_authenticate(user=self.customer_user)

        # GET passenger list
        list_url = reverse("bookings:passenger-list", kwargs={"booking_reference": booking.booking_reference})
        res_list = self.client.get(list_url)
        self.assertEqual(res_list.status_code, status.HTTP_200_OK)
        data_list = res_list.json()["data"]
        # Paginated or direct list
        passengers = data_list["results"] if isinstance(data_list, dict) and "results" in data_list else data_list
        self.assertEqual(len(passengers), 1)
        self.assertEqual(passengers[0]["full_name"], "John Doe")

        # PATCH passenger detail
        detail_url = reverse(
            "bookings:passenger-detail",
            kwargs={"booking_reference": booking.booking_reference, "passenger_id": passenger.id},
        )
        patch_payload = {
            "dietary_requirements": "Strict Vegan & Gluten Free",
        }
        res_patch = self.client.patch(detail_url, patch_payload, format="json")
        self.assertEqual(res_patch.status_code, status.HTTP_200_OK)
        self.assertEqual(res_patch.json()["data"]["dietary_requirements"], "Strict Vegan & Gluten Free")

        # Updating passport expiry to an invalid date (< 180 days) is rejected
        res_invalid_patch = self.client.patch(
            detail_url,
            {"passport_expiry_date": str(self.invalid_passport_expiry)},
            format="json",
        )
        self.assertEqual(res_invalid_patch.status_code, status.HTTP_400_BAD_REQUEST)
