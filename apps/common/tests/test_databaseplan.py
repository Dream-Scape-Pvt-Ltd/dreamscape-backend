from datetime import date, timedelta
from decimal import Decimal
import uuid
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.accounts.models import UserRole
from apps.accounts.serializers.user_serializers import (
    UserRegistrationSerializer,
    UserProfileSerializer,
)
from apps.destinations.models import Destination, DestinationCountry, ActivityCategory
from apps.trips.models import (
    Trip,
    DifficultyGrade,
    PeakExpeditionDetail,
    ItineraryDay,
    AccommodationType,
    TripDeparture,
    DepartureStatus,
    TripReview,
)
from apps.trips.serializers.trip_serializers import TripListSerializer, TripDetailSerializer
from apps.bookings.models import Booking, BookingStatus, PaymentType, PassengerDetail
from apps.bookings.serializers.booking_serializers import BookingCreateSerializer, BookingDetailSerializer
from apps.payments.models import (
    PaymentTransaction,
    PaymentGateway,
    PaymentStage,
    PaymentStatus,
    PaymentActionToken,
)
from apps.payments.serializers.payment_serializers import (
    PaymentInitiateSerializer,
    PaymentWebhookSerializer,
)
from apps.inquiries.models import Inquiry, InquiryType, InquiryStatus, TailorMadeRequest, InquiryNote
from apps.inquiries.serializers.inquiry_serializers import InquiryCreateSerializer, InquiryDetailSerializer
from apps.b2b.models import B2BPartner, AgencyTier, B2BAsset, AssetType, B2BBooking, CommissionStatus
from apps.b2b.serializers.asset_serializers import B2BAssetSerializer
from apps.content_cms.models import TravelGuide, GuideCategory, ResponsibleTravelInitiative
from apps.content_cms.serializers.guide_serializers import TravelGuideDetailSerializer
from apps.faq.models import FAQ, FAQCategory
from apps.faq.serializers.faq_serializers import FAQSerializer
from apps.search.services import perform_global_search

User = get_user_model()


class DatabaseArchitectureTestCase(TestCase):
    """
    Comprehensive test suite validating the complete database & serialization architecture
    as specified in databaseplan.md.
    """

    def setUp(self):
        # Create standard test users
        self.admin_user = User.objects.create_superuser(
            email="admin@dreamscape-treks.com",
            password="AdminPassword123!",
            first_name="Super",
            last_name="Admin",
        )
        self.agent_user = User.objects.create_user(
            email="agent@dreamscape-treks.com",
            password="AgentPassword123!",
            first_name="Tenzing",
            last_name="Sherpa",
            role=UserRole.SALES_AGENT,
        )
        self.customer_user = User.objects.create_user(
            email="traveler@example.com",
            password="CustomerPassword123!",
            first_name="Sarah",
            last_name="Jenkins",
            role=UserRole.CUSTOMER,
        )

        # Create destination & category
        self.destination = Destination.objects.create(
            name="Everest Region",
            slug="everest-region",
            country=DestinationCountry.NEPAL,
            region_name="Khumbu",
            visa_guidelines="On-arrival visa available at Tribhuvan International Airport (TIA), Kathmandu.",
            permit_details="Sagarmatha National Park Permit & Khumbu Pasang Lhamu Rural Municipality Permit required.",
            is_active=True,
        )
        self.category = ActivityCategory.objects.create(
            name="High Altitude Trekking",
            slug="high-altitude-trekking",
            description="Challenging high pass and base camp treks.",
            is_active=True,
        )

        # Create trip
        self.trip = Trip.objects.create(
            destination=self.destination,
            category=self.category,
            title="Everest Base Camp & Gokyo Lakes",
            slug="everest-base-camp-gokyo-lakes",
            duration_days=16,
            altitude_max_meters=5364,
            difficulty_grade=DifficultyGrade.GRADE_4,
            min_group_size=2,
            max_group_size=12,
            best_seasons=["SPRING", "AUTUMN"],
            inclusions=["All tea-house accommodation", "TIMS and National Park permits", "Licensed guide and porters"],
            exclusions=["International flights", "Travel insurance", "Personal gear"],
            packing_list=["4-season sleeping bag", "Down jacket", "Trekking boots"],
            starting_price_usd=Decimal("1850.00"),
            single_supplement_usd=Decimal("350.00"),
            overview="An iconic 16-day loop taking in both Everest Base Camp and the emerald Gokyo Lakes.",
            is_featured=True,
            is_active=True,
        )

        # Create Itinerary Days
        self.day1 = ItineraryDay.objects.create(
            trip=self.trip,
            day_number=1,
            title="Fly Kathmandu to Lukla, Trek to Phakding",
            description="Scenic 35-minute mountain flight followed by an easy 3-hour trek down to Phakding.",
            overnight_stay="Phakding",
            elevation_meters=2610,
            accommodation_type=AccommodationType.TEAHOUSE,
            is_acclimatization_day=False,
            meals_included=["L", "D"],
            latitude=Decimal("27.7402000"),
            longitude=Decimal("86.7132000"),
        )
        self.day2 = ItineraryDay.objects.create(
            trip=self.trip,
            day_number=2,
            title="Trek Phakding to Namche Bazaar",
            description="Cross suspension bridges over the Dudh Koshi river and climb to the Sherpa capital.",
            overnight_stay="Namche Bazaar",
            elevation_meters=3440,
            accommodation_type=AccommodationType.TEAHOUSE,
            is_acclimatization_day=False,
            meals_included=["B", "L", "D"],
            latitude=Decimal("27.8069000"),
            longitude=Decimal("86.7140000"),
        )

        # Create departure
        self.departure = TripDeparture.objects.create(
            trip=self.trip,
            start_date=date.today() + timedelta(days=60),
            end_date=date.today() + timedelta(days=76),
            price_usd=Decimal("1850.00"),
            max_seats=12,
            available_seats=12,
            status=DepartureStatus.GUARANTEED,
            is_guaranteed=True,
        )

    # 1. Accounts & RBAC
    def test_custom_user_model_and_manager(self):
        user = User.objects.create_user(
            email="testuser@example.com",
            password="SecureTestPassword123!",
            first_name="Jane",
            last_name="Doe",
        )
        self.assertEqual(user.email, "testuser@example.com")
        self.assertEqual(user.role, UserRole.CUSTOMER)
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertEqual(user.full_name, "Jane Doe")
        self.assertTrue(user.check_password("SecureTestPassword123!"))

        # Test duplicate email rejection
        with self.assertRaises(IntegrityError):
            User.objects.create_user(
                email="testuser@example.com",
                password="AnotherPassword123!",
            )

    def test_superuser_creation(self):
        self.assertTrue(self.admin_user.is_superuser)
        self.assertTrue(self.admin_user.is_staff)
        self.assertEqual(self.admin_user.role, UserRole.ADMIN)

    # 2. Destinations & Trips Models & Constraints
    def test_itinerary_day_unique_constraint(self):
        # Attempting to create duplicate day_number for same trip must fail
        with self.assertRaises(IntegrityError):
            ItineraryDay.objects.create(
                trip=self.trip,
                day_number=1,
                title="Duplicate Day 1",
                description="Should fail",
            )

    def test_trip_departure_seats_constraint(self):
        # Negative available seats must violate CheckConstraint
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                TripDeparture.objects.create(
                    trip=self.trip,
                    start_date=date.today() + timedelta(days=10),
                    end_date=date.today() + timedelta(days=20),
                    price_usd=Decimal("1000.00"),
                    max_seats=10,
                    available_seats=-1,  # Invalid!
                )

    def test_trip_departure_dates_constraint(self):
        # end_date before start_date must violate CheckConstraint
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                TripDeparture.objects.create(
                    trip=self.trip,
                    start_date=date.today() + timedelta(days=30),
                    end_date=date.today() + timedelta(days=20),  # Invalid!
                    price_usd=Decimal("1000.00"),
                    max_seats=10,
                    available_seats=10,
                )

    def test_review_rating_constraint_and_verified_signal(self):
        # Overall rating must be between 1 and 5
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                TripReview.objects.create(
                    trip=self.trip,
                    reviewer_name="Invalid Rating User",
                    rating_overall=6,  # Invalid!
                    content="Great trip!",
                )

        # Create valid booking
        booking = Booking.objects.create(
            booking_reference="DS-2026-REV01",
            customer_user=self.customer_user,
            departure=self.departure,
            customer_name="Sarah Jenkins",
            customer_email=self.customer_user.email,
            num_travelers=1,
            total_amount_usd=Decimal("1850.00"),
            deposit_amount_usd=Decimal("370.00"),
            balance_amount_usd=Decimal("1480.00"),
            amount_paid_usd=Decimal("1850.00"),
            status=BookingStatus.FULLY_PAID,
            trip_start_date=self.departure.start_date,
        )

        review = TripReview.objects.create(
            trip=self.trip,
            user=self.customer_user,
            booking=booking,
            reviewer_name="Sarah Jenkins",
            rating_overall=5,
            title="Life changing experience",
            content="Everest Base Camp was unforgettable.",
            is_verified=True,
            is_published=True,
        )
        self.assertTrue(review.is_verified)

        # Disassociate booking -> verified badge must be revoked by signal
        review.booking = None
        review.save()
        review.refresh_from_db()
        self.assertFalse(review.is_verified)

    # 3. Bookings & Passengers
    def test_booking_financial_guards(self):
        # Total amount <= 0 must fail CheckConstraint
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Booking.objects.create(
                    booking_reference="DS-2026-NEG01",
                    customer_name="Test",
                    customer_email="test@example.com",
                    num_travelers=1,
                    total_amount_usd=Decimal("-10.00"),  # Invalid!
                    deposit_amount_usd=Decimal("0.00"),
                    balance_amount_usd=Decimal("0.00"),
                    amount_paid_usd=Decimal("0.00"),
                    trip_start_date=date.today(),
                )

    def test_booking_create_serializer_with_seat_lock(self):
        initial_seats = self.departure.available_seats
        serializer = BookingCreateSerializer(
            data={
                "departure_id": str(self.departure.id),
                "customer_name": "Mark Wilson",
                "customer_email": "mark@example.com",
                "payment_type": PaymentType.DEPOSIT_20,
                "passengers": [
                    {
                        "full_name": "Mark Wilson",
                        "gender": "Male",
                        "date_of_birth": "1990-05-15",
                        "passport_number": "PA9876543",
                        "passport_expiry_date": (self.departure.start_date + timedelta(days=250)).isoformat(),
                        "nationality": "British",
                        "insurance_provider": "World Nomads",
                        "insurance_policy_number": "WN-889900",
                        "insurance_emergency_phone": "+44 20 7946 0991",
                    }
                ],
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        booking = serializer.save()

        # Confirm seat deduction
        self.departure.refresh_from_db()
        self.assertEqual(self.departure.available_seats, initial_seats - 1)

        # Confirm 20% deposit and balance computation
        expected_total = Decimal("1850.00")
        expected_deposit = (expected_total * Decimal("0.20")).quantize(Decimal("0.01"))
        expected_balance = expected_total - expected_deposit
        self.assertEqual(booking.total_amount_usd, expected_total)
        self.assertEqual(booking.deposit_amount_usd, expected_deposit)
        self.assertEqual(booking.balance_amount_usd, expected_balance)
        self.assertEqual(booking.balance_due_date, self.departure.start_date - timedelta(days=7))
        self.assertEqual(booking.passengers.count(), 1)

    # 4. Payments
    def test_payment_initiate_and_webhook_transition(self):
        booking = Booking.objects.create(
            booking_reference="DS-2026-PAY01",
            customer_user=self.customer_user,
            departure=self.departure,
            customer_name="Sarah Jenkins",
            customer_email="traveler@example.com",
            num_travelers=1,
            total_amount_usd=Decimal("1850.00"),
            deposit_amount_usd=Decimal("370.00"),
            balance_amount_usd=Decimal("1480.00"),
            amount_paid_usd=Decimal("0.00"),
            status=BookingStatus.PENDING,
            trip_start_date=self.departure.start_date,
        )

        init_serializer = PaymentInitiateSerializer(
            data={
                "booking_id": str(booking.id),
                "gateway": PaymentGateway.KHALTI,
                "payment_stage": PaymentStage.DEPOSIT_20,
            }
        )
        self.assertTrue(init_serializer.is_valid(), init_serializer.errors)
        session_data = init_serializer.save()
        txn_id = session_data["transaction_id"]

        # Simulate webhook callback
        webhook_serializer = PaymentWebhookSerializer(
            data={
                "transaction_id": txn_id,
                "gateway_status": "Completed",
                "idempotency_key": f"IDEMP-{uuid.uuid4().hex[:8]}",
                "raw_payload": {"state": "Completed", "idx": "Khalti-Idx-123"},
            }
        )
        self.assertTrue(webhook_serializer.is_valid(), webhook_serializer.errors)
        txn = webhook_serializer.save()

        self.assertEqual(txn.status, PaymentStatus.SUCCESS)
        booking.refresh_from_db()
        self.assertEqual(booking.status, BookingStatus.DEPOSIT_PAID)
        self.assertEqual(booking.amount_paid_usd, Decimal("370.00"))

    # 5. Inquiries & CRM
    def test_inquiry_create_with_tailor_made(self):
        serializer = InquiryCreateSerializer(
            data={
                "inquiry_type": InquiryType.TAILOR_MADE,
                "full_name": "David Miller",
                "email": "david@example.com",
                "phone": "+1 555 123 4567",
                "message": "Looking for custom 14-day trek including Langtang and Gosainkunda.",
                "group_size": 4,
                "estimated_budget": Decimal("8000.00"),
                "tailor_made_detail": {
                    "custom_destinations": ["Langtang", "Gosainkunda", "Helambu"],
                    "desired_activities": ["High passes", "Lake exploration", "Monastery visits"],
                    "fitness_level": "Advanced",
                    "accommodation_standard": "Comfort Teahouses",
                },
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        inquiry = serializer.save()

        self.assertTrue(inquiry.inquiry_number.startswith("INQ-2026-"))
        self.assertIsNotNone(inquiry.tailor_made_detail)
        self.assertEqual(len(inquiry.tailor_made_detail.custom_destinations), 3)

    # 6. B2B Partner & Assets
    def test_b2b_partner_and_tier_gating(self):
        partner_user = User.objects.create_user(
            email="partner@alpine-expeditions.co.uk",
            password="B2BPartnerSecret123!",
            first_name="Arthur",
            last_name="Pendleton",
            role=UserRole.B2B_PARTNER,
        )
        partner = B2BPartner.objects.create(
            user=partner_user,
            company_name="Alpine Expeditions UK",
            country="United Kingdom",
            agency_tier=AgencyTier.SILVER,
            commission_rate=Decimal("15.00"),
            approved=True,
        )

        bronze_asset = B2BAsset.objects.create(
            trip=self.trip,
            title="EBC Bronze White Label Itinerary",
            asset_type=AssetType.WHITE_LABEL_ITINERARY,
            file="b2b_assets/ebc_bronze.pdf",
            minimum_tier=AgencyTier.BRONZE,
        )
        platinum_asset = B2BAsset.objects.create(
            trip=self.trip,
            title="EBC Platinum Unbranded 4K B-Roll",
            asset_type=AssetType.MARKETING_MEDIA,
            file="b2b_assets/ebc_4k.mp4",
            minimum_tier=AgencyTier.PLATINUM,
        )

        from rest_framework.test import APIRequestFactory
        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = partner_user

        context = {"request": request}
        bronze_data = B2BAssetSerializer(bronze_asset, context=context).data
        platinum_data = B2BAssetSerializer(platinum_asset, context=context).data

        self.assertTrue(bronze_data["is_accessible"])
        self.assertFalse(platinum_data["is_accessible"])

    # 7. Content CMS & FAQ
    def test_travel_guide_and_schema_org(self):
        guide = TravelGuide.objects.create(
            destination=self.destination,
            author=self.admin_user,
            title="Ultimate Guide to Everest Trekking Permits 2026",
            slug="everest-trekking-permits-guide-2026",
            country="Nepal",
            region="Khumbu",
            category=GuideCategory.PERMITS,
            markdown_content="# Permits Required\n\n1. Sagarmatha National Park\n2. Khumbu Municipality Card",
            is_published=True,
        )
        self.assertIsNotNone(guide.published_at)

        serializer = TravelGuideDetailSerializer(guide)
        data = serializer.data
        self.assertIn("schema_org_article", data)
        self.assertEqual(data["schema_org_article"]["@type"], "Article")

    def test_faq_and_schema_org(self):
        faq = FAQ.objects.create(
            trip=self.trip,
            question="What happens if I get altitude sickness in Dingboche?",
            answer="Our guides carry pulse oximeters and supplementary oxygen. Immediate descent is initiated if symptoms persist.",
            category=FAQCategory.TREKKING,
            display_order=1,
            is_active=True,
        )
        serializer = FAQSerializer(faq)
        data = serializer.data
        self.assertEqual(data["schema_org_json_ld"]["@type"], "Question")
        self.assertEqual(data["schema_org_json_ld"]["name"], faq.question)

    # 8. Global Full-Text Search
    def test_global_full_text_search(self):
        results = perform_global_search("Everest")
        self.assertTrue(len(results) > 0)
        types_found = {r["entity_type"] for r in results}
        self.assertIn("trip", types_found)
