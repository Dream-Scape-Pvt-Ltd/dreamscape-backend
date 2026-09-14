from rest_framework import serializers
from apps.trips.models import DepartureStatus, TripDeparture


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


class TripDepartureWriteSerializer(serializers.ModelSerializer):
    """
    Admin serializer for scheduling and updating departures.
    Enforces seat bounds and date integrity rules.
    """

    available_seats = serializers.IntegerField(required=False)

    class Meta:
        model = TripDeparture
        fields = [
            "id",
            "trip",
            "start_date",
            "end_date",
            "price_usd",
            "max_seats",
            "available_seats",
            "status",
            "is_guaranteed",
        ]
        read_only_fields = ["id", "trip"]

    def validate(self, attrs):
        start_date = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end_date = attrs.get("end_date", getattr(self.instance, "end_date", None))
        max_seats = attrs.get("max_seats", getattr(self.instance, "max_seats", None))
        available_seats = attrs.get("available_seats", getattr(self.instance, "available_seats", None))

        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({"end_date": "End date cannot precede start date."})

        if available_seats is None and max_seats is not None:
            attrs["available_seats"] = max_seats
            available_seats = max_seats

        if max_seats is not None and available_seats is not None:
            if available_seats > max_seats:
                raise serializers.ValidationError({"available_seats": "Available seats cannot exceed max seats."})
            if available_seats < 0:
                raise serializers.ValidationError({"available_seats": "Available seats cannot be negative."})

        return attrs
