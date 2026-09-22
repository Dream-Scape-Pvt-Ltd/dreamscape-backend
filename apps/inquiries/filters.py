import uuid

import django_filters
from django.db.models import Q
from rest_framework.exceptions import ValidationError

from apps.inquiries.models import Inquiry, InquiryStatus, InquiryType


class InquiryFilter(django_filters.FilterSet):
    """
    CRM lead pipeline filter.

    Replaces hand-rolled query-param parsing so that a malformed value returns
    400 rather than reaching the database. ``assigned_agent`` keeps the ``me``
    sentinel the admin UI relies on.
    """

    trip = django_filters.CharFilter(field_name="trip__slug", lookup_expr="iexact")
    departure = django_filters.UUIDFilter(field_name="departure_id")
    destination = django_filters.CharFilter(
        field_name="trip__destination__slug", lookup_expr="iexact"
    )
    status = django_filters.ChoiceFilter(choices=InquiryStatus.choices)
    inquiry_type = django_filters.ChoiceFilter(choices=InquiryType.choices)
    assigned_agent = django_filters.CharFilter(method="filter_by_agent")
    lead_source = django_filters.CharFilter(lookup_expr="iexact")
    sla_breached = django_filters.BooleanFilter()
    tag = django_filters.CharFilter(field_name="tags__name", lookup_expr="iexact")
    created_after = django_filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    created_before = django_filters.DateFilter(field_name="created_at", lookup_expr="date__lte")
    departure_after = django_filters.DateFilter(
        field_name="departure__start_date", lookup_expr="gte"
    )
    departure_before = django_filters.DateFilter(
        field_name="departure__start_date", lookup_expr="lte"
    )
    search = django_filters.CharFilter(method="filter_by_search")

    class Meta:
        model = Inquiry
        fields = [
            "trip",
            "departure",
            "destination",
            "status",
            "inquiry_type",
            "assigned_agent",
            "lead_source",
            "sla_breached",
            "tag",
            "created_after",
            "created_before",
            "departure_after",
            "departure_before",
            "search",
        ]

    def filter_by_agent(self, queryset, name, value):
        value = (value or "").strip()
        if not value:
            return queryset
        if value.lower() == "me":
            user = getattr(self.request, "user", None)
            if not user or not user.is_authenticated:
                return queryset.none()
            return queryset.filter(assigned_agent=user)
        if value.lower() in ("none", "unassigned"):
            return queryset.filter(assigned_agent__isnull=True)
        try:
            uuid.UUID(value)
        except (ValueError, AttributeError, TypeError):
            # Without this the bad value reaches the database and 500s.
            raise ValidationError(
                {"assigned_agent": ["Enter a valid UUID, 'me', or 'unassigned'."]}
            )
        return queryset.filter(assigned_agent_id=value)

    def filter_by_search(self, queryset, name, value):
        value = (value or "").strip()
        if not value:
            return queryset
        return queryset.filter(
            Q(full_name__icontains=value)
            | Q(email__icontains=value)
            | Q(inquiry_number__icontains=value)
        )
