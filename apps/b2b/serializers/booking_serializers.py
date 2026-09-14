from rest_framework import serializers
from apps.b2b.models import B2BBooking, CommissionStatus
from django.utils import timezone


class B2BBookingSerializer(serializers.ModelSerializer):
    """
    Partner net ledger serializer.
    Shows gross vs commission vs net payable for agency group bookings.
    """

    booking_reference = serializers.CharField(source="booking.booking_reference", read_only=True)
    trip_title = serializers.SerializerMethodField()
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

    def get_trip_title(self, obj) -> str | None:
        if obj.booking.departure_id:
            return obj.booking.departure.trip.title
        if obj.booking.custom_trip_id:
            return obj.booking.custom_trip.title
        return None


class B2BCommissionUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = B2BBooking
        fields = ['commission_status']

    def update(self, instance, validated_data):
        new_status = validated_data['commission_status']
        now = timezone.now()
        if new_status == CommissionStatus.INVOICED and not instance.commission_invoiced_at:
            instance.commission_invoiced_at = now
        if new_status == CommissionStatus.PAID and not instance.commission_paid_at:
            instance.commission_paid_at = now
        if new_status != CommissionStatus.PAID:
            instance.commission_paid_at = None
        return super().update(instance, validated_data)
