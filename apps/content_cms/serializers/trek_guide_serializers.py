from rest_framework import serializers
from apps.content_cms.models import TrekGuide
from apps.destinations.models import Destination
from apps.trips.models import Trip

MAX_LIST_ITEMS = 20
MAX_ITEM_LENGTH = 120


def clean_text_list(value, label):
    """Languages and certifications: a short list of short, non-empty strings, de-duplicated in order."""
    if not isinstance(value, list):
        raise serializers.ValidationError(f"{label} must be a list.")
    if len(value) > MAX_LIST_ITEMS:
        raise serializers.ValidationError(f"Add at most {MAX_LIST_ITEMS} {label.lower()}.")
    cleaned = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise serializers.ValidationError(f"Each entry in {label.lower()} must be text.")
        text = item.strip()
        if len(text) > MAX_ITEM_LENGTH:
            raise serializers.ValidationError(f"Keep each entry in {label.lower()} under {MAX_ITEM_LENGTH} characters.")
        if text not in cleaned:
            cleaned.append(text)
    return cleaned


class TrekGuideRegionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Destination
        fields = ["id", "slug", "name"]


class TrekGuideTripSerializer(serializers.ModelSerializer):
    destination_name = serializers.CharField(source="destination.name", read_only=True)
    destination_slug = serializers.CharField(source="destination.slug", read_only=True)
    destination_id = serializers.UUIDField(source="destination.id", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)
    category_slug = serializers.CharField(source="category.slug", read_only=True)

    class Meta:
        model = Trip
        fields = [
            "id", "slug", "title", "duration_days", "difficulty_grade", "starting_price_usd", "altitude_max_meters",
            "hero_image_url", "destination_name", "destination_slug", "destination_id", "category_name", "category_slug",
        ]


class TrekGuideListSerializer(serializers.ModelSerializer):
    regions = TrekGuideRegionSerializer(many=True, read_only=True)

    class Meta:
        model = TrekGuide
        fields = [
            "id", "slug", "name", "role", "photo_url", "years_experience", "languages",
            "regions", "is_published", "display_order",
        ]


class TrekGuideDetailSerializer(TrekGuideListSerializer):
    treks_led = serializers.SerializerMethodField()

    class Meta(TrekGuideListSerializer.Meta):
        fields = TrekGuideListSerializer.Meta.fields + ["bio", "certifications", "treks_led"]

    def get_treks_led(self, guide):
        # The public never sees inactive treks, even if a guide is still linked to them.
        trips = [trip for trip in guide.treks_led.all() if trip.is_active]
        return TrekGuideTripSerializer(trips, many=True).data


class TrekGuideWriteSerializer(serializers.ModelSerializer):
    regions = serializers.SlugRelatedField(slug_field="slug", queryset=Destination.objects.all(), many=True, required=False)
    treks_led = serializers.SlugRelatedField(slug_field="slug", queryset=Trip.objects.all(), many=True, required=False)

    class Meta:
        model = TrekGuide
        fields = [
            "slug", "name", "role", "photo_url", "bio", "years_experience", "languages",
            "certifications", "regions", "treks_led", "is_published", "display_order",
        ]

    def validate_languages(self, value):
        return clean_text_list(value, "Languages")

    def validate_certifications(self, value):
        return clean_text_list(value, "Certifications")

    def validate_years_experience(self, value):
        if value is not None and value > 80:
            raise serializers.ValidationError("Enter the number of years, up to 80.")
        return value


class TrekGuideSummarySerializer(serializers.ModelSerializer):
    """The short form shown on a trek's page."""

    class Meta:
        model = TrekGuide
        fields = ["id", "slug", "name", "role", "photo_url"]
