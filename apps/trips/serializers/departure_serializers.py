from rest_framework import serializers
from apps.trips.models import TripDeparture


class TripDepartureSerializer(serializers.ModelSerializer):
    """
    Public calendar departure seats serializer.
    ORM Dependencies: select_related('trip') when accessed standalone.

    ``available_seats`` and ``availability_state`` are derived from the seat
    ledger on the model, so the shape of this response is unchanged from when
    ``available_seats`` was a stored column.
    """

    available_seats = serializers.IntegerField(read_only=True)
    availability_state = serializers.CharField(read_only=True)

    class Meta:
        model = TripDeparture
        fields = [
            "id",
            "start_date",
            "end_date",
            "price_usd",
            "max_seats",
            "available_seats",
            "availability_state",
            "status",
            "is_guaranteed",
            "waitlist_enabled",
        ]


class DepartureCapacitySerializer(serializers.ModelSerializer):
    """
    Admin capacity view of a departure: the full seat breakdown plus live
    demand counters.

    ``open_inquiry_count`` and ``waitlisted_count`` must be annotated onto the
    queryset by the view (see ``TripDepartureQuerySet.with_capacity_counts``);
    they fall back to 0 so a non-annotated instance still serializes.
    """

    trip_title = serializers.CharField(source="trip.title", read_only=True)
    trip_slug = serializers.CharField(source="trip.slug", read_only=True)
    available_seats = serializers.IntegerField(read_only=True)
    utilization_pct = serializers.IntegerField(read_only=True)
    availability_state = serializers.CharField(read_only=True)
    open_inquiry_count = serializers.IntegerField(read_only=True, default=0)
    waitlisted_count = serializers.IntegerField(read_only=True, default=0)
    capacity_state = serializers.SerializerMethodField()

    class Meta:
        model = TripDeparture
        fields = [
            "id",
            "trip_title",
            "trip_slug",
            "start_date",
            "end_date",
            "price_usd",
            "max_seats",
            "booked_seats",
            "reserved_seats",
            "available_seats",
            "utilization_pct",
            "open_inquiry_count",
            "waitlisted_count",
            "capacity_state",
            "availability_state",
            "status",
            "status_locked",
            "waitlist_enabled",
            "few_seats_threshold",
            "is_guaranteed",
        ]
        read_only_fields = fields

    def get_capacity_state(self, obj) -> str:
        """
        HEALTHY | NEARLY_FULL | FULL | OVERSUBSCRIBED

        Computed server-side so the admin board, the CRM board, and any future
        alerting all agree on what "nearly full" means.
        """
        open_inquiries = getattr(obj, "open_inquiry_count", 0) or 0
        committed = obj.booked_seats + obj.reserved_seats
        if open_inquiries + committed > obj.max_seats:
            return "OVERSUBSCRIBED"
        if obj.available_seats <= 0:
            return "FULL"
        if obj.available_seats <= obj.few_seats_threshold:
            return "NEARLY_FULL"
        return "HEALTHY"


class TripDepartureWriteSerializer(serializers.ModelSerializer):
    """
    Admin serializer for scheduling and updating departures.

    ``booked_seats`` is deliberately read-only: it belongs to the booking flow,
    which mutates it under a row lock. Admins adjust capacity through
    ``max_seats`` and ``reserved_seats``.
    """

    available_seats = serializers.IntegerField(read_only=True)
    booked_seats = serializers.IntegerField(read_only=True)

    class Meta:
        model = TripDeparture
        fields = [
            "id",
            "trip",
            "start_date",
            "end_date",
            "price_usd",
            "max_seats",
            "booked_seats",
            "reserved_seats",
            "available_seats",
            "few_seats_threshold",
            "waitlist_enabled",
            "status_locked",
            "status",
            "is_guaranteed",
        ]
        read_only_fields = ["id", "trip", "booked_seats", "available_seats"]

    def validate(self, attrs):
        def resolved(name, default=None):
            if name in attrs:
                return attrs[name]
            return getattr(self.instance, name, default)

        start_date = resolved("start_date")
        end_date = resolved("end_date")
        max_seats = resolved("max_seats")
        reserved_seats = resolved("reserved_seats", 0) or 0
        booked_seats = getattr(self.instance, "booked_seats", 0) or 0

        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({"end_date": "End date cannot precede start date."})

        if max_seats is not None:
            if reserved_seats > max_seats:
                raise serializers.ValidationError(
                    {"reserved_seats": "Reserved seats cannot exceed max seats."}
                )
            # An admin must not be able to reserve or shrink seats out from
            # under travellers who already hold a confirmed booking.
            if booked_seats + reserved_seats > max_seats:
                raise serializers.ValidationError({
                    "max_seats": (
                        f"{booked_seats} seat(s) are already booked and {reserved_seats} "
                        f"reserved, which exceeds a capacity of {max_seats}. "
                        f"Cancel bookings or lower reserved seats first."
                    )
                })

        return attrs

    def update(self, instance, validated_data):
        departure = super().update(instance, validated_data)
        if departure.recompute_status():
            departure.save(update_fields=["status", "updated_at"])
        return departure

    def create(self, validated_data):
        departure = super().create(validated_data)
        if departure.recompute_status():
            departure.save(update_fields=["status", "updated_at"])
        return departure
