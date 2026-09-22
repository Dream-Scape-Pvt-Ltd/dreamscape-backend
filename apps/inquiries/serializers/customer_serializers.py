from rest_framework import serializers

from apps.inquiries.models import Customer


class CustomerInquirySummarySerializer(serializers.Serializer):
    """
    Compact inquiry summary embedded in the customer-360 view — avoids a
    circular import with InquiryListSerializer by declaring fields directly.
    """

    id = serializers.UUIDField()
    inquiry_number = serializers.CharField()
    inquiry_type = serializers.CharField()
    status = serializers.CharField()
    trip_title = serializers.CharField(source="trip.title", default=None)
    created_at = serializers.DateTimeField()


class CustomerBookingSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    booking_reference = serializers.CharField()
    status = serializers.CharField()
    total_amount_usd = serializers.DecimalField(max_digits=12, decimal_places=2)
    trip_start_date = serializers.DateField()
    created_at = serializers.DateTimeField()


class CustomerSerializer(serializers.ModelSerializer):
    """
    Customer-360 view: identity, lifetime stats, and every inquiry +
    booking made under this email address.
    """

    inquiries = serializers.SerializerMethodField()
    bookings = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = [
            "id",
            "email",
            "full_name",
            "phone",
            "whatsapp_number",
            "lifetime_inquiries",
            "lifetime_bookings",
            "lifetime_value_usd",
            "inquiries",
            "bookings",
            "created_at",
        ]
        read_only_fields = fields

    def get_inquiries(self, obj) -> list:
        qs = obj.inquiries.select_related("trip").order_by("-created_at")[:50]
        return CustomerInquirySummarySerializer(qs, many=True).data

    def get_bookings(self, obj) -> list:
        from apps.bookings.models import Booking

        qs = Booking.objects.filter(customer_email__iexact=obj.email).order_by("-created_at")[:50]
        return CustomerBookingSummarySerializer(qs, many=True).data
