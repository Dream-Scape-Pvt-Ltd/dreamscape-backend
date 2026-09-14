from rest_framework import serializers
from apps.inquiries.models import TailorMadeRequest


class TailorMadeRequestSerializer(serializers.ModelSerializer):
    """
    Serializer for tailor-made custom adventure specifications,
    including bespoke destinations, activity desires, and GeoJSON route coordinates.
    """

    class Meta:
        model = TailorMadeRequest
        fields = [
            "id",
            "custom_destinations",
            "desired_activities",
            "fitness_level",
            "accommodation_standard",
            "guide_language_preference",
            "custom_route_coordinates",
            "waypoints",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


# Alias for backward compatibility
TailorMadeRequestCreateSerializer = TailorMadeRequestSerializer
