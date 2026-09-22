from django.db import transaction
from rest_framework import serializers

from apps.bookings.models import DepartureWaitlistEntry, WaitlistStatus
from apps.bookings.services import join_waitlist
from apps.trips.models import TripDeparture


class WaitlistEntrySerializer(serializers.ModelSerializer):
    """Read serializer for a waitlist entry, returned on join and to admins."""

    trip_title = serializers.CharField(source="departure.trip.title", read_only=True)
    trip_slug = serializers.CharField(source="departure.trip.slug", read_only=True)
    start_date = serializers.DateField(source="departure.start_date", read_only=True)
    end_date = serializers.DateField(source="departure.end_date", read_only=True)

    class Meta:
        model = DepartureWaitlistEntry
        fields = [
            "id",
            "departure",
            "trip_title",
            "trip_slug",
            "start_date",
            "end_date",
            "customer_name",
            "customer_email",
            "customer_phone",
            "num_travelers",
            "position",
            "status",
            "offered_at",
            "offer_expires_at",
            "created_at",
        ]
        read_only_fields = fields


class WaitlistJoinSerializer(serializers.Serializer):
    """
    Public write serializer for joining a full departure's waitlist.

    Deliberately light on data compared to a booking: no passports, no payment.
    The full passenger detail is collected later, if and when the traveller
    claims an offered seat.
    """

    departure_id = serializers.UUIDField(required=True)
    customer_name = serializers.CharField(max_length=255)
    customer_email = serializers.EmailField()
    customer_phone = serializers.CharField(max_length=50, required=False, allow_blank=True)
    num_travelers = serializers.IntegerField(min_value=1, default=1)

    def validate(self, attrs):
        try:
            departure = TripDeparture.objects.select_related("trip").get(
                id=attrs["departure_id"]
            )
        except TripDeparture.DoesNotExist:
            raise serializers.ValidationError(
                {"departure_id": "Selected departure does not exist."}
            )

        if not departure.waitlist_enabled:
            raise serializers.ValidationError(
                {"departure_id": "This departure is not accepting waitlist entries."}
            )
        if departure.status == "CANCELLED":
            raise serializers.ValidationError(
                {"departure_id": "This departure has been cancelled."}
            )
        if attrs["num_travelers"] > departure.max_seats:
            raise serializers.ValidationError({
                "num_travelers": (
                    f"This departure holds at most {departure.max_seats} travellers."
                )
            })

        attrs["_departure"] = departure
        return attrs

    def create(self, validated_data):
        departure = validated_data.pop("_departure")
        validated_data.pop("departure_id")

        request = self.context.get("request")
        customer_user = (
            request.user if request and request.user.is_authenticated else None
        )

        with transaction.atomic():
            locked = TripDeparture.objects.select_for_update().get(id=departure.id)
            return join_waitlist(
                locked,
                customer_name=validated_data["customer_name"],
                customer_email=validated_data["customer_email"],
                customer_phone=validated_data.get("customer_phone", ""),
                num_travelers=validated_data["num_travelers"],
                customer_user=customer_user,
            )
