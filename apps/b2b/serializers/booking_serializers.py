from rest_framework import serializers
from apps.b2b.models import B2BBooking


class B2BBookingSerializer(serializers.ModelSerializer):
    """
    Partner net ledger serializer.
    Shows gross vs commission vs net payable for agency group bookings.
    """

    booking_reference = serializers.CharField(source="booking.booking_reference", read_only=True)
    trip_title = serializers.CharField(source="booking.departure.trip.title", read_only=True)
    num_travelers = serializers.IntegerField(source="booking.num_travelers", read_only=True)
    trip_start_date = serializers.DateField(source="booking.trip_start_date", read_only=True)

    class Meta:
        model = B2BBooking
        fields = [
            "id",
            "booking",
            "booking_reference",
            "trip_title",
            "num_travelers",
            "trip_start_date",
            "gross_amount_usd",
            "commission_rate",
            "commission_amount_usd",
            "net_amount_usd",
            "commission_status",
            "commission_invoiced_at",
            "commission_paid_at",
            "created_at",
        ]
        read_only_fields = fields
