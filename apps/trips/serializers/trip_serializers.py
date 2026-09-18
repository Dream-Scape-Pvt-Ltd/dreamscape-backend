from django.db.models import Avg
from rest_framework import serializers

from apps.destinations.serializers.category_serializers import ActivityCategorySerializer
from apps.destinations.serializers.destination_serializers import DestinationListSerializer
from apps.trips.models import PeakExpeditionDetail, Trip
from apps.trips.serializers.departure_serializers import TripDepartureSerializer
from apps.trips.serializers.itinerary_serializers import ItineraryDaySerializer
from apps.trips.serializers.review_serializers import TripReviewReadSerializer


class PeakExpeditionDetailSerializer(serializers.ModelSerializer):
    """
    Expedition mountaineering metadata serializer.
    """

    class Meta:
        model = PeakExpeditionDetail
        fields = [
            "id",
            "summit_window",
            "technical_rating",
            "gear_requirements",
            "permit_fee_type",
            "mandatory_certifications",
        ]
        read_only_fields = ["id"]


class TripListSerializer(serializers.ModelSerializer):
    """
    Serializer for search catalog and filter cards.
    ORM Dependencies: select_related('destination', 'category')
    """

    destination_name = serializers.CharField(source="destination.name", read_only=True)
    destination_slug = serializers.CharField(source="destination.slug", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)
    category_slug = serializers.CharField(source="category.slug", read_only=True)
    rating_avg = serializers.SerializerMethodField()
    reviews_count = serializers.SerializerMethodField()

    class Meta:
        model = Trip
        fields = [
            "id",
            "title",
            "slug",
            "destination_name",
            "destination_slug",
            "category_name",
            "category_slug",
            "duration_days",
            "starting_price_usd",
            "altitude_max_meters",
            "difficulty_grade",
            "hero_image_url",
            "gallery_images",
            "is_featured",
            "is_highlighted",
            "highlight_order",
            "is_active",
            "rating_avg",
            "reviews_count",
        ]
        read_only_fields = fields

    def get_rating_avg(self, obj) -> float | None:
        if hasattr(obj, "rating_avg") and obj.rating_avg is not None:
            return round(float(obj.rating_avg), 1)
        avg = obj.reviews.filter(is_published=True).aggregate(Avg("rating_overall"))["rating_overall__avg"]
        return round(float(avg), 1) if avg else None

    def get_reviews_count(self, obj) -> int:
        if hasattr(obj, "reviews_count"):
            return obj.reviews_count
        return obj.reviews.filter(is_published=True).count()


class TripDetailSerializer(serializers.ModelSerializer):
    """
    Complete trip detail view with rich nested relations and Schema.org TouristTrip JSON-LD.
    ORM Dependencies:
        select_related: 'destination', 'category', 'expedition_detail'
        prefetch_related: 'itinerary_days', 'departures', 'reviews'
    """

    destination = DestinationListSerializer(read_only=True)
    category = ActivityCategorySerializer(read_only=True)
    expedition_detail = PeakExpeditionDetailSerializer(read_only=True)
    itinerary_days = ItineraryDaySerializer(many=True, read_only=True)
    departures = serializers.SerializerMethodField()
    reviews = serializers.SerializerMethodField()
    rating_summary = serializers.SerializerMethodField()
    schema_org_json_ld = serializers.SerializerMethodField()

    class Meta:
        model = Trip
        fields = [
            "id",
            "title",
            "slug",
            "destination",
            "category",
            "duration_days",
            "altitude_max_meters",
            "difficulty_grade",
            "min_group_size",
            "max_group_size",
            "best_seasons",
            "inclusions",
            "exclusions",
            "packing_list",
            "starting_price_usd",
            "single_supplement_usd",
            "overview",
            "hero_image_url",
            "gallery_images",
            "is_featured",
            "is_active",
            "expedition_detail",
            "itinerary_days",
            "departures",
            "reviews",
            "rating_summary",
            "schema_org_json_ld",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_departures(self, obj):
        departures = obj.departures.filter(available_seats__gt=0).order_by("start_date")[:10]
        return TripDepartureSerializer(departures, many=True).data

    def get_reviews(self, obj):
        reviews = obj.reviews.filter(is_published=True).order_by("-created_at")[:10]
        return TripReviewReadSerializer(reviews, many=True).data

    def get_rating_summary(self, obj):
        reviews = obj.reviews.filter(is_published=True)
        count = reviews.count()
        if count == 0:
            return {"average_rating": None, "total_reviews": 0}
        avg = reviews.aggregate(Avg("rating_overall"))["rating_overall__avg"]
        return {
            "average_rating": round(float(avg), 1) if avg else None,
            "total_reviews": count,
        }

    def get_schema_org_json_ld(self, obj):
        rating_summary = self.get_rating_summary(obj)
        schema = {
            "@context": "https://schema.org",
            "@type": "TouristTrip",
            "name": obj.title,
            "description": obj.overview[:250] if obj.overview else obj.title,
            "touristType": obj.category.name if obj.category else "Trekking",
            "offers": {
                "@type": "Offer",
                "price": str(obj.starting_price_usd),
                "priceCurrency": "USD",
                "availability": "https://schema.org/InStock",
            },
        }
        if rating_summary["total_reviews"] > 0:
            schema["aggregateRating"] = {
                "@type": "AggregateRating",
                "ratingValue": str(rating_summary["average_rating"]),
                "reviewCount": str(rating_summary["total_reviews"]),
                "bestRating": "5",
                "worstRating": "1",
            }
        return schema


class TripWriteSerializer(serializers.ModelSerializer):
    """
    Admin serializer for creating and updating Trip records.
    """

    class Meta:
        model = Trip
        fields = [
            "id",
            "destination",
            "category",
            "title",
            "slug",
            "duration_days",
            "altitude_max_meters",
            "difficulty_grade",
            "min_group_size",
            "max_group_size",
            "best_seasons",
            "inclusions",
            "exclusions",
            "packing_list",
            "starting_price_usd",
            "single_supplement_usd",
            "overview",
            "hero_image_url",
            "gallery_images",
            "is_featured",
            "is_highlighted",
            "highlight_order",
            "is_active",
        ]
        read_only_fields = ["id"]


class TripHighlightUpdateSerializer(serializers.Serializer):
    """
    Validates selection of up to 5 highlighted treks/tours.
    Accepts trip_ids (UUID) or trip_slugs (str).
    """

    trip_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        max_length=5,
        min_length=1,
        help_text="List of up to 5 trip UUIDs in desired highlight order."
    )
    trip_slugs = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        max_length=5,
        min_length=1,
        help_text="List of up to 5 trip slugs in desired highlight order."
    )

    def validate(self, attrs):
        trip_ids = attrs.get("trip_ids")
        trip_slugs = attrs.get("trip_slugs")

        if not trip_ids and not trip_slugs:
            raise serializers.ValidationError("Either 'trip_ids' or 'trip_slugs' must be provided.")

        if trip_ids:
            if len(trip_ids) > 5:
                raise serializers.ValidationError({"trip_ids": "You can highlight at most 5 trips."})
            if len(trip_ids) != len(set(trip_ids)):
                raise serializers.ValidationError({"trip_ids": "Duplicate trip IDs are not allowed."})

            trips = list(Trip.objects.filter(id__in=trip_ids, is_active=True))
            found_ids = {trip.id for trip in trips}
            missing = [str(tid) for tid in trip_ids if tid not in found_ids]
            if missing:
                raise serializers.ValidationError({
                    "trip_ids": f"The following trip IDs were not found or are inactive: {', '.join(missing)}"
                })
            id_map = {trip.id: trip for trip in trips}
            attrs["_resolved_trips"] = [id_map[tid] for tid in trip_ids]

        elif trip_slugs:
            if len(trip_slugs) > 5:
                raise serializers.ValidationError({"trip_slugs": "You can highlight at most 5 trips."})
            if len(trip_slugs) != len(set(trip_slugs)):
                raise serializers.ValidationError({"trip_slugs": "Duplicate trip slugs are not allowed."})

            trips = list(Trip.objects.filter(slug__in=trip_slugs, is_active=True))
            found_slugs = {trip.slug for trip in trips}
            missing = [slug for slug in trip_slugs if slug not in found_slugs]
            if missing:
                raise serializers.ValidationError({
                    "trip_slugs": f"The following trip slugs were not found or are inactive: {', '.join(missing)}"
                })
            slug_map = {trip.slug: trip for trip in trips}
            attrs["_resolved_trips"] = [slug_map[slug] for slug in trip_slugs]

        return attrs

