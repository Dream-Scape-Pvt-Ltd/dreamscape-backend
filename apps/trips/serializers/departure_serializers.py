from rest_framework import serializers
from apps.trips.models import TripDeparture


class TripDepartureSerializer(serializers.ModelSerializer):
    """
    Calendar departure seats serializer.
    ORM Dependencies: select_related('trip') when accessed standalone.
    """

    class Meta:
        model = TripDeparture
        fields = [
            "id",
            "start_date",
            "end_date",
            "price_usd",
            "max_seats",
            "available_seats",
            "status",
            "is_guaranteed",
        ]
