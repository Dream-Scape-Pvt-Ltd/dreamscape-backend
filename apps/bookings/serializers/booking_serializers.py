from datetime import timedelta
from decimal import Decimal
from django.db import transaction
from rest_framework import serializers

from apps.bookings.models import Booking, PassengerDetail, PaymentType, BookingStatus
from apps.bookings.serializers.passenger_serializers import PassengerDetailSerializer
from apps.bookings.utils import generate_booking_reference
from apps.common.exceptions import SeatsUnavailableError
from apps.trips.models import TripDeparture, DepartureStatus
from apps.trips.serializers.departure_serializers import TripDepartureSerializer


class BookingCreateSerializer(serializers.Serializer):
    """
    Write serializer for booking checkout and seat reservation.
    Uses database-level row locking (select_for_update) to guarantee seat availability.
    Enforces atomic split-payment calculation (DEPOSIT_20 vs FULL_100) and passenger validation.
    """

    departure_id = serializers.UUIDField(required=True)
    customer_name = serializers.CharField(max_length=255)
    customer_email = serializers.EmailField()
    customer_phone = serializers.CharField(max_length=50, required=False, allow_blank=True)
    payment_type = serializers.ChoiceField(
        choices=PaymentType.choices,
        default=PaymentType.DEPOSIT_20,
    )
    passengers = PassengerDetailSerializer(many=True, required=True)

    def validate_passengers(self, value):
        if not value:
            raise serializers.ValidationError("At least one passenger must be provided.")
        return value

    def validate(self, attrs):
        departure_id = attrs.get("departure_id")
        try:
            departure = TripDeparture.objects.get(id=departure_id)
        except TripDeparture.DoesNotExist:
            raise serializers.ValidationError({"departure_id": "Selected departure does not exist."})

        num_travelers = len(attrs.get("passengers", []))
        if departure.available_seats < num_travelers:
            raise SeatsUnavailableError()

        # Enforce passenger passport validity: minimum 6 months (180 days) from departure start_date
        six_months_ahead = departure.start_date + timedelta(days=180)
        for idx, passenger in enumerate(attrs.get("passengers", [])):
            passport_expiry = passenger.get("passport_expiry_date")
            if passport_expiry and passport_expiry < six_months_ahead:
                p_name = passenger.get("full_name", f"Passenger {idx + 1}")
                raise serializers.ValidationError({
                    "passengers": (
                        f"{p_name}'s passport expiry date ({passport_expiry}) must be valid for at least "
                        f"6 months after trip departure date ({departure.start_date}). "
                        f"Minimum required expiry: {six_months_ahead}."
                    )
                })

        attrs["_departure"] = departure
        return attrs

    def create(self, validated_data):
        departure_id = validated_data.pop("departure_id")
        passengers_data = validated_data.pop("passengers")
        validated_data.pop("_departure", None)
        num_travelers = len(passengers_data)

        request = self.context.get("request")
        customer_user = request.user if request and request.user.is_authenticated else None

        with transaction.atomic():
            # Acquire exclusive row lock on departure
            departure = TripDeparture.objects.select_for_update().get(id=departure_id)

            if departure.available_seats < num_travelers:
                raise SeatsUnavailableError()

            # Deduct seats atomically
            departure.available_seats -= num_travelers
            if departure.available_seats == 0:
                departure.status = DepartureStatus.SOLD_OUT
            departure.save(update_fields=["available_seats", "status", "updated_at"])

            # Calculate finances
            unit_price = departure.price_usd
            total_amount = (unit_price * Decimal(num_travelers)).quantize(Decimal("0.01"))
            payment_type = validated_data.get("payment_type", PaymentType.DEPOSIT_20)

            if payment_type == PaymentType.FULL_100:
                deposit_amount = total_amount
                balance_amount = Decimal("0.00")
            else:
                deposit_amount = (total_amount * Decimal("0.20")).quantize(Decimal("0.01"))
                balance_amount = total_amount - deposit_amount

            trip_start = departure.start_date
            balance_due_date = trip_start - timedelta(days=7)

            booking_ref = generate_booking_reference()
            while Booking.objects.filter(booking_reference=booking_ref).exists():
                booking_ref = generate_booking_reference()

            booking = Booking.objects.create(
                booking_reference=booking_ref,
                customer_user=customer_user,
                departure=departure,
                num_travelers=num_travelers,
                total_amount_usd=total_amount,
                deposit_amount_usd=deposit_amount,
                balance_amount_usd=balance_amount,
                amount_paid_usd=Decimal("0.00"),
                status=BookingStatus.PENDING,
                trip_start_date=trip_start,
                balance_due_date=balance_due_date,
                **validated_data,
            )

            # Create passenger records
            passenger_objects = [
                PassengerDetail(booking=booking, **p_data)
                for p_data in passengers_data
            ]
            PassengerDetail.objects.bulk_create(passenger_objects)

        return booking


class BookingListSerializer(serializers.ModelSerializer):
    """
    Compact read serializer for traveler dashboard and staff listing views.
    """

    trip_title = serializers.SerializerMethodField()
    trip_slug = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = [
            "id",
            "booking_reference",
            "customer_name",
            "customer_email",
            "trip_title",
            "trip_slug",
            "trip_start_date",
            "balance_due_date",
            "num_travelers",
            "currency",
            "payment_type",
            "total_amount_usd",
            "deposit_amount_usd",
            "balance_amount_usd",
            "amount_paid_usd",
            "status",
            "created_at",
        ]

    def get_trip_title(self, obj) -> str | None:
        if obj.departure and obj.departure.trip:
            return obj.departure.trip.title
        if obj.custom_trip:
            return obj.custom_trip.title
        return None

    def get_trip_slug(self, obj) -> str | None:
        if obj.departure and obj.departure.trip:
            return obj.departure.trip.slug
        if obj.custom_trip:
            return obj.custom_trip.slug
        return None


class BookingDetailSerializer(serializers.ModelSerializer):
    """
    Full read serializer for booking confirmation and detailed lifecycle tracking.
    ORM Dependencies:
        select_related: 'departure__trip', 'customer_user'
        prefetch_related: 'passengers'
    """

    departure = TripDepartureSerializer(read_only=True)
    passengers = PassengerDetailSerializer(many=True, read_only=True)
    trip_title = serializers.SerializerMethodField()
    trip_slug = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = [
            "id",
            "booking_reference",
            "customer_name",
            "customer_email",
            "customer_phone",
            "trip_title",
            "trip_slug",
            "departure",
            "num_travelers",
            "currency",
            "payment_type",
            "total_amount_usd",
            "deposit_amount_usd",
            "balance_amount_usd",
            "amount_paid_usd",
            "status",
            "trip_start_date",
            "balance_due_date",
            "cancellation_reason",
            "passengers",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_trip_title(self, obj) -> str | None:
        if obj.departure and obj.departure.trip:
            return obj.departure.trip.title
        if obj.custom_trip:
            return obj.custom_trip.title
        return None

    def get_trip_slug(self, obj) -> str | None:
        if obj.departure and obj.departure.trip:
            return obj.departure.trip.slug
        if obj.custom_trip:
            return obj.custom_trip.slug
        return None


class BookingCancelSerializer(serializers.Serializer):
    """
    Write serializer for booking cancellation.
    Restores departure seats atomically and marks booking as CANCELLED.
    """

    cancellation_reason = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=1000,
    )

    def validate(self, attrs):
        booking = self.context.get("booking")
        if not booking:
            raise serializers.ValidationError("Booking not found.")
        if booking.status == BookingStatus.CANCELLED:
            raise serializers.ValidationError("Booking is already cancelled.")
        return attrs

    def cancel_booking(self):
        booking = self.context["booking"]
        cancellation_reason = self.validated_data.get("cancellation_reason", "")

        with transaction.atomic():
            locked_booking = Booking.objects.select_for_update().get(id=booking.id)
            if locked_booking.status == BookingStatus.CANCELLED:
                raise serializers.ValidationError("Booking is already cancelled.")

            if locked_booking.departure_id:
                departure = TripDeparture.objects.select_for_update().get(id=locked_booking.departure_id)
                departure.available_seats = min(
                    departure.available_seats + locked_booking.num_travelers,
                    departure.max_seats,
                )
                if departure.status == DepartureStatus.SOLD_OUT and departure.available_seats > 0:
                    departure.status = DepartureStatus.GUARANTEED if departure.is_guaranteed else DepartureStatus.LIMITED
                departure.save(update_fields=["available_seats", "status", "updated_at"])

            locked_booking.status = BookingStatus.CANCELLED
            locked_booking.cancellation_reason = cancellation_reason
            locked_booking.save(update_fields=["status", "cancellation_reason", "updated_at"])

        return locked_booking
