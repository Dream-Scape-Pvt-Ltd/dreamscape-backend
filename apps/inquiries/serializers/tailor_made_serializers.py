from rest_framework import serializers
from apps.inquiries.models import TailorMadeRequest


class TailorMadeRequestCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for tailor-made custom trip requests with interactive map waypoints.
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
        ]
