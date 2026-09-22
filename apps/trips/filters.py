import django_filters
from django.db.models import F, Q
from apps.trips.models import DepartureStatus, DifficultyGrade, Trip, TripDeparture


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


class DepartureCapacityFilter(django_filters.FilterSet):
    """
    Cross-trip filter for the admin capacity board.

    Expects a queryset already passed through
    ``TripDepartureQuerySet.with_capacity_counts()`` — ``capacity_state``
    filters on the ``seats_left`` and ``open_inquiry_count`` annotations.
    """

    trip = django_filters.CharFilter(field_name="trip__slug", lookup_expr="iexact")
    destination = django_filters.CharFilter(
        field_name="trip__destination__slug", lookup_expr="iexact"
    )
    status = django_filters.ChoiceFilter(choices=DepartureStatus.choices)
    start_after = django_filters.DateFilter(field_name="start_date", lookup_expr="gte")
    start_before = django_filters.DateFilter(field_name="start_date", lookup_expr="lte")
    capacity_state = django_filters.ChoiceFilter(
        choices=[
            ("HEALTHY", "Healthy"),
            ("NEARLY_FULL", "Nearly Full"),
            ("FULL", "Full"),
            ("OVERSUBSCRIBED", "Oversubscribed"),
        ],
        method="filter_by_capacity_state",
    )

    class Meta:
        model = TripDeparture
        fields = [
            "trip",
            "destination",
            "status",
            "start_after",
            "start_before",
            "capacity_state",
        ]

    def filter_by_capacity_state(self, queryset, name, value):
        # Mirrors DepartureCapacitySerializer.get_capacity_state. Oversubscribed
        # is checked first there too, so the two orderings agree.
        oversubscribed = Q(
            open_inquiry_count__gt=F("max_seats") - F("booked_seats") - F("reserved_seats")
        )
        if value == "OVERSUBSCRIBED":
            return queryset.filter(oversubscribed)
        if value == "FULL":
            return queryset.filter(seats_left__lte=0).exclude(oversubscribed)
        if value == "NEARLY_FULL":
            return queryset.filter(
                seats_left__gt=0, seats_left__lte=F("few_seats_threshold")
            ).exclude(oversubscribed)
        if value == "HEALTHY":
            return queryset.filter(seats_left__gt=F("few_seats_threshold")).exclude(
                oversubscribed
            )
        return queryset
