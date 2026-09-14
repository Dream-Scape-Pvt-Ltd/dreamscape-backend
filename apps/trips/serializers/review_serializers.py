from rest_framework import serializers

from apps.bookings.models import Booking
from apps.trips.models import TripReview


class TripReviewReadSerializer(serializers.ModelSerializer):
    """
    Public customer reviews serializer.
    ORM Dependencies: select_related('user', 'booking') when needed.
    """

    class Meta:
        model = TripReview
        fields = [
            "id",
            "reviewer_name",
            "reviewer_country",
            "rating_overall",
            "rating_guide",
            "rating_itinerary",
            "rating_safety",
            "title",
            "content",
            "travel_date",
            "is_verified",
            "created_at",
        ]
        read_only_fields = fields


class TripReviewCreateSerializer(serializers.ModelSerializer):
    """
    Customer review creation serializer.
    Validates overall rating (1-5) and links confirmed booking belonging to request.user to grant verified badge.
    """

    booking_id = serializers.UUIDField(required=False, allow_null=True)

    class Meta:
        model = TripReview
        fields = [
            "trip",
            "booking_id",
            "reviewer_name",
            "reviewer_country",
            "rating_overall",
            "rating_guide",
            "rating_itinerary",
            "rating_safety",
            "title",
            "content",
            "travel_date",
        ]

    def validate_rating_overall(self, value):
        if not (1 <= value <= 5):
            raise serializers.ValidationError("Rating overall must be between 1 and 5.")
        return value

    def create(self, validated_data):
        booking_id = validated_data.pop("booking_id", None)
        request = self.context.get("request")
        user = request.user if request and request.user.is_authenticated else None

        is_verified = False
        booking = None
        if booking_id:
            try:
                booking = Booking.objects.get(id=booking_id)
                # Verify that the booking belongs to this user or matching email
                if user and booking.customer_user == user:
                    is_verified = True
                elif booking.customer_email and user and booking.customer_email.lower() == user.email.lower():
                    is_verified = True
            except Booking.DoesNotExist:
                raise serializers.ValidationError({"booking_id": "Specified booking was not found."})

        # By default in production, new reviews require moderation (is_published=False)
        review = TripReview.objects.create(
            user=user,
            booking=booking,
            is_verified=is_verified,
            is_published=False,
            **validated_data,
        )
        return review


class TripReviewModerationSerializer(serializers.ModelSerializer):
    """
    Admin serializer for moderating and publishing reviews.
    """

    class Meta:
        model = TripReview
        fields = [
            "id",
            "is_published",
            "is_verified",
        ]
        read_only_fields = ["id"]
