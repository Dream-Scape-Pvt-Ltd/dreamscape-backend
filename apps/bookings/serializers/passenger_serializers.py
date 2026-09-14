from datetime import timedelta
from rest_framework import serializers
from apps.bookings.models import PassengerDetail


class PassengerDetailSerializer(serializers.ModelSerializer):
    """
    Passenger manifest serializer.
    Enforces minimum 6 months (180 days) passport validity beyond trip start date.
    """

    class Meta:
        model = PassengerDetail
        fields = [
            "id",
            "full_name",
            "gender",
            "date_of_birth",
            "passport_number",
            "passport_expiry_date",
            "nationality",
            "insurance_provider",
            "insurance_policy_number",
            "insurance_emergency_phone",
            "emergency_contact_name",
            "emergency_contact_phone",
            "dietary_requirements",
            "medical_conditions",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        passport_expiry = attrs.get("passport_expiry_date")
        if not passport_expiry and self.instance:
            passport_expiry = self.instance.passport_expiry_date

        trip_start = self.context.get("trip_start_date")
        if not trip_start:
            booking = self.context.get("booking") or getattr(self.instance, "booking", None)
            if booking and booking.trip_start_date:
                trip_start = booking.trip_start_date

        if trip_start and passport_expiry:
            six_months_ahead = trip_start + timedelta(days=180)
            if passport_expiry < six_months_ahead:
                raise serializers.ValidationError({
                    "passport_expiry_date": (
                        f"Passport must be valid for at least 6 months after trip departure date "
                        f"({trip_start}). Minimum required expiry: {six_months_ahead}."
                    )
                })
        return attrs
