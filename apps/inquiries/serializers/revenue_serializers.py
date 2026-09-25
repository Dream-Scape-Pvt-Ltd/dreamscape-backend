from rest_framework import serializers

from apps.inquiries.models import RevenueEntry
from apps.trips.models import Trip


class RevenueEntrySerializer(serializers.ModelSerializer):
    trip_id = serializers.PrimaryKeyRelatedField(
        queryset=Trip.objects.all(), source="trip", required=False, allow_null=True
    )
    trip_title = serializers.CharField(source="trip.title", read_only=True, default=None)
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = RevenueEntry
        fields = [
            "id", "amount_usd", "earned_on", "description",
            "trip_id", "trip_title", "created_by_name", "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_created_by_name(self, entry):
        user = entry.created_by
        if not user:
            return None
        return user.get_full_name() or user.email

    def validate_description(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Describe what this revenue is for.")
        return value
