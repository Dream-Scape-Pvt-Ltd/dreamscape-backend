import secrets
from datetime import timedelta
from decimal import Decimal
from django.db import transaction
from rest_framework import serializers

from apps.bookings.models import Booking, PassengerDetail, PaymentType, BookingStatus
from apps.bookings.serializers.passenger_serializers import PassengerDetailSerializer
from apps.trips.models import TripDeparture
from apps.trips.serializers.departure_serializers import TripDepartureSerializer


def generate_booking_reference() -> str:
    """Generate reference in format DS-2026-X8B9Q"""
    random_suffix = secrets.token_hex(3).upper()[:5]
    return f"DS-2026-{random_suffix}"


class BookingCreateSerializer(serializers.Serializer):
    """
    Write serializer for booking checkout and seat reservation.
    Uses database-level row locking (select_for_update) to guarantee seat availability.
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

    def create(self, validated_data):
        departure_id = validated_data.pop("departure_id")
        passengers_data = validated_data.pop("passengers")
        num_travelers = len(passengers_data)

        request = self.context.get("request")
        customer_user = request.user if request and request.user.is_authenticated else None

        with transaction.atomic():
            departure = TripDeparture.objects.select_for_update().get(id=departure_id)

            if departure.available_seats < num_travelers:
                raise serializers.ValidationError(
                    f"Not enough seats available. Requested {num_travelers}, only {departure.available_seats} remaining."
                )

            # Deduct seats atomically
            departure.available_seats -= num_travelers
            departure.save(update_fields=["available_seats", "updated_at"])

            # Compute finances
            unit_price = departure.price_usd
            total_amount = unit_price * Decimal(num_travelers)

            if validated_data.get("payment_type") == PaymentType.FULL_100:
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

            # Create passengers
            for p_data in passengers_data:
                PassengerDetail.objects.create(booking=booking, **p_data)

        return booking


class BookingDetailSerializer(serializers.ModelSerializer):
    """
    Read serializer for traveler booking confirmation and lifecycle tracking.
    ORM Dependencies:
        select_related: 'departure__trip', 'customer_user'
        prefetch_related: 'passengers', 'payments'
    """

    departure = TripDepartureSerializer(read_only=True)
    passengers = PassengerDetailSerializer(many=True, read_only=True)
    trip_title = serializers.CharField(source="departure.trip.title", read_only=True)

    class Meta:
        model = Booking
        fields = [
            "id",
            "booking_reference",
            "customer_name",
            "customer_email",
            "customer_phone",
            "trip_title",
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
            "passengers",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
