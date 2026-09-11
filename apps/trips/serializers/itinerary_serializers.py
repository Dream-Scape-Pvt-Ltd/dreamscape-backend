from rest_framework import serializers
from apps.trips.models import ItineraryDay


class ItineraryDaySerializer(serializers.ModelSerializer):
    """
    Day-by-day trail data serializer.
    Includes altitude coordinates (elevation_meters, latitude, longitude, is_acclimatization_day).
    """

    class Meta:
        model = ItineraryDay
        fields = [
            "id",
            "day_number",
            "title",
            "description",
            "overnight_stay",
            "elevation_meters",
            "accommodation_type",
            "is_acclimatization_day",
            "meals_included",
            "latitude",
            "longitude",
        ]
