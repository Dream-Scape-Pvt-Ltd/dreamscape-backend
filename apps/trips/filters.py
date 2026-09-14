import django_filters
from django.db.models import Q
from apps.trips.models import DifficultyGrade, Trip


class TripFilter(django_filters.FilterSet):
    """
    Multi-faceted catalog filter for treks and expeditions.
    Supports filtering by destination slug, country, activity category slug,
    difficulty grade, duration range, altitude range, price range, and seasons.
    """

    destination = django_filters.CharFilter(field_name="destination__slug", lookup_expr="iexact")
    country = django_filters.CharFilter(field_name="destination__country", lookup_expr="iexact")
    category = django_filters.CharFilter(field_name="category__slug", lookup_expr="iexact")
    difficulty_grade = django_filters.ChoiceFilter(choices=DifficultyGrade.choices)

    min_duration = django_filters.NumberFilter(field_name="duration_days", lookup_expr="gte")
    max_duration = django_filters.NumberFilter(field_name="duration_days", lookup_expr="lte")

    min_altitude = django_filters.NumberFilter(field_name="altitude_max_meters", lookup_expr="gte")
    max_altitude = django_filters.NumberFilter(field_name="altitude_max_meters", lookup_expr="lte")

    min_price = django_filters.NumberFilter(field_name="starting_price_usd", lookup_expr="gte")
    max_price = django_filters.NumberFilter(field_name="starting_price_usd", lookup_expr="lte")

    season = django_filters.CharFilter(method="filter_by_season")
    is_featured = django_filters.BooleanFilter(field_name="is_featured")

    class Meta:
        model = Trip
        fields = [
            "destination",
            "country",
            "category",
            "difficulty_grade",
            "min_duration",
            "max_duration",
            "min_altitude",
            "max_altitude",
            "min_price",
            "max_price",
            "season",
            "is_featured",
        ]

    def filter_by_season(self, queryset, name, value):
        if not value:
            return queryset
        # JSONField containment check for season string (e.g., 'Spring', 'Autumn')
        return queryset.filter(best_seasons__icontains=value.strip())
