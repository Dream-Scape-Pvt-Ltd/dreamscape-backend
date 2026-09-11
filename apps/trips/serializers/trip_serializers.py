from django.db.models import Avg
from rest_framework import serializers

from apps.destinations.serializers.destination_serializers import DestinationListSerializer
from apps.destinations.serializers.category_serializers import ActivityCategorySerializer
from apps.trips.models import Trip, PeakExpeditionDetail
from apps.trips.serializers.itinerary_serializers import ItineraryDaySerializer
from apps.trips.serializers.departure_serializers import TripDepartureSerializer
from apps.trips.serializers.review_serializers import TripReviewReadSerializer


class PeakExpeditionDetailSerializer(serializers.ModelSerializer):
    """
    Expedition mountaineering metadata serializer.
    """

    class Meta:
        model = PeakExpeditionDetail
        fields = [
            "summit_window",
            "technical_rating",
            "gear_requirements",
            "permit_fee_type",
            "mandatory_certifications",
        ]


class TripListSerializer(serializers.ModelSerializer):
    """
    Serializer for search catalog and filter cards.
    ORM Dependencies: select_related('destination', 'category')
    """

    destination_name = serializers.CharField(source="destination.name", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = Trip
        fields = [
            "id",
            "title",
            "slug",
            "destination_name",
            "category_name",
            "duration_days",
            "starting_price_usd",
            "altitude_max_meters",
            "difficulty_grade",
            "is_featured",
            "is_active",
        ]
        read_only_fields = fields


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
        # Upcoming available departures
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
        return {
            "@context": "https://schema.org",
            "@type": "TouristTrip",
            "name": obj.title,
            "description": obj.overview[:200] if obj.overview else obj.title,
            "touristType": obj.category.name if obj.category else "Trekking",
            "offers": {
                "@type": "Offer",
                "price": str(obj.starting_price_usd),
                "priceCurrency": "USD",
                "availability": "https://schema.org/InStock",
            },
        }
