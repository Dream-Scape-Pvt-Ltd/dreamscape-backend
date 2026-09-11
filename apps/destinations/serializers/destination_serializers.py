from rest_framework import serializers
from apps.destinations.models import Destination


class DestinationListSerializer(serializers.ModelSerializer):
    """
    Serializer for destination catalog cards and filter options.
    """

    class Meta:
        model = Destination
        fields = [
            "id",
            "name",
            "slug",
            "country",
            "region_name",
            "hero_media",
            "is_active",
        ]
        read_only_fields = fields


class DestinationDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for full destination landing page with trips count and SEO metadata.
    Query dependency: annotated with trips_count or prefetches trips.
    """

    trips_count = serializers.SerializerMethodField()
    meta_title = serializers.SerializerMethodField()
    meta_description = serializers.SerializerMethodField()

    class Meta:
        model = Destination
        fields = [
            "id",
            "name",
            "slug",
            "country",
            "region_name",
            "visa_guidelines",
            "permit_details",
            "hero_media",
            "trips_count",
            "meta_title",
            "meta_description",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_trips_count(self, obj) -> int:
        if hasattr(obj, "trips_count"):
            return obj.trips_count
        return obj.trips.filter(is_active=True).count()

    def get_meta_title(self, obj) -> str:
        return f"Explore {obj.name}, {obj.get_country_display()} — Dreamscape Treks"

    def get_meta_description(self, obj) -> str:
        snippet = obj.visa_guidelines[:150] if obj.visa_guidelines else f"Discover hand-crafted treks and expeditions across {obj.name}."
        return snippet
