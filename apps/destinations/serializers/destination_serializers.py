from rest_framework import serializers

from apps.destinations.models import Destination


class DestinationListSerializer(serializers.ModelSerializer):
    """
    Serializer for destination catalog cards and filter options.
    ORM Dependency: annotated with trips_count or via method.
    """

    trips_count = serializers.SerializerMethodField()

    class Meta:
        model = Destination
        fields = [
            "id",
            "name",
            "slug",
            "country",
            "region_name", "headline", "description", "highlights", "trail_style", "pace", "base", "mood",
            "hero_media",
            "gallery_images",
            "trips_count",
            "is_active",
        ]
        read_only_fields = fields

    def get_trips_count(self, obj) -> int:
        if hasattr(obj, "trips_count"):
            return obj.trips_count
        return obj.trips.filter(is_active=True).count()


class DestinationDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for full destination landing page with trips count and Schema.org metadata.
    Query dependency: annotated with trips_count or prefetches trips.
    """

    trips_count = serializers.SerializerMethodField()
    meta_title = serializers.SerializerMethodField()
    meta_description = serializers.SerializerMethodField()
    schema_org_json_ld = serializers.SerializerMethodField()

    class Meta:
        model = Destination
        fields = [
            "id",
            "name",
            "slug",
            "country",
            "region_name", "headline", "description", "highlights", "trail_style", "pace", "base", "mood",
            "visa_guidelines",
            "permit_details",
            "hero_media",
            "gallery_images",
            "trips_count",
            "meta_title",
            "meta_description",
            "schema_org_json_ld",
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
        if obj.visa_guidelines:
            return obj.visa_guidelines[:160].strip()
        return f"Discover hand-crafted treks, tours and expeditions across {obj.name}."

    def get_schema_org_json_ld(self, obj) -> dict:
        return {
            "@context": "https://schema.org",
            "@type": "TouristDestination",
            "name": obj.name,
            "description": obj.visa_guidelines[:250] if obj.visa_guidelines else f"Trekking in {obj.name}",
            "containedInPlace": {
                "@type": "Country",
                "name": obj.get_country_display(),
            },
        }


class DestinationWriteSerializer(serializers.ModelSerializer):
    """
    Admin serializer for creating and updating destinations.
    """

    class Meta:
        model = Destination
        fields = [
            "id",
            "name",
            "slug",
            "country",
            "region_name", "headline", "description", "highlights", "trail_style", "pace", "base", "mood",
            "visa_guidelines",
            "permit_details",
            "hero_media",
            "gallery_images",
            "is_active",
        ]
        read_only_fields = ["id"]

    def validate_gallery_images(self, images):
        if not isinstance(images, list) or len(images) > 12:
            raise serializers.ValidationError("Provide up to 12 photo URLs.")
        if not all(isinstance(image, str) and image.startswith(("http://", "https://")) for image in images):
            raise serializers.ValidationError("Each photo must have an HTTP or HTTPS URL.")
        return images
