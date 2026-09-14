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
            "is_featured",
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
            "is_featured",
            "is_active",
        ]
        read_only_fields = ["id"]
