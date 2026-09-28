from rest_framework import serializers
from apps.trips.models import ItineraryDay


class ItineraryDaySerializer(serializers.ModelSerializer):
    """
    Day-by-day trail data serializer.
    Includes altitude coordinates (elevation_meters, latitude, longitude, is_acclimatization_day).
    """

    description = serializers.CharField(required=False, allow_blank=True, default="")
    day_number = serializers.IntegerField(min_value=1)
    elevation_meters = serializers.IntegerField(min_value=0, max_value=8849, allow_null=True, required=False)

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


def validated_itinerary(data):
    """Validate a full CMS replacement before changing any saved itinerary rows."""
    if 'itinerary_days' not in data:
        return None
    days = data['itinerary_days']
    if not isinstance(days, list) or len(days) > 120:
        raise serializers.ValidationError({'itinerary_days': 'Provide a list of up to 120 itinerary days.'})
    serializer = ItineraryDaySerializer(data=days, many=True)
    serializer.is_valid(raise_exception=True)
    numbers = [day['day_number'] for day in serializer.validated_data]
    if len(numbers) != len(set(numbers)):
        raise serializers.ValidationError({'itinerary_days': 'Day numbers must be unique.'})
    return serializer.validated_data
