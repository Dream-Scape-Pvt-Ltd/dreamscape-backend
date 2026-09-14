from django.db.models import Avg, Count, Q
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import generics, status
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.common.permissions import IsAdminRole
from apps.trips.filters import TripFilter
from apps.trips.models import Trip
from apps.trips.serializers import (
    TripDetailSerializer,
    TripListSerializer,
    TripWriteSerializer,
)


class TripListCreateView(generics.ListCreateAPIView):
    """
    Catalog of treks, tours, and expeditions.
    Supports comprehensive filtering (destination, activity, difficulty, duration, altitude, price, season).
    Admins can create new trips.
    """

    filterset_class = TripFilter
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["title", "overview", "destination__name", "destination__region_name"]
    ordering_fields = ["starting_price_usd", "duration_days", "altitude_max_meters", "created_at"]

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAdminRole()]
        return [AllowAny()]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return TripWriteSerializer
        return TripListSerializer

    def get_queryset(self):
        qs = Trip.objects.select_related("destination", "category").annotate(
            rating_avg=Avg("reviews__rating_overall", filter=Q(reviews__is_published=True)),
            reviews_count=Count("reviews", filter=Q(reviews__is_published=True)),
        )
        # Admins can view all trips including inactive ones
        if self.request.user.is_authenticated and getattr(self.request.user, "role", None) == "ADMIN":
            return qs.order_by("-is_featured", "title")

        return qs.filter(is_active=True).order_by("-is_featured", "title")

    @extend_schema(
        tags=["Trips"],
        responses={200: TripListSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        response.success_message = "Trips retrieved successfully."
        return response

    @extend_schema(
        tags=["Trips Admin"],
        request=TripWriteSerializer,
        responses={
            201: TripDetailSerializer,
            400: OpenApiResponse(description="Validation error."),
            403: OpenApiResponse(description="Forbidden: Admin role required."),
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        trip = serializer.save()
        output_serializer = TripDetailSerializer(trip)
        response = Response(output_serializer.data, status=status.HTTP_201_CREATED)
        response.success_message = "Trip created successfully."
        return response


class TripDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Complete trip details by slug, including itineraries, departures, reviews,
    and Schema.org TouristTrip JSON-LD.
    Admins can update or delete trips.
    """

    lookup_field = "slug"

    def get_permissions(self):
        if self.request.method in ["PATCH", "PUT", "DELETE"]:
            return [IsAdminRole()]
        return [AllowAny()]

    def get_serializer_class(self):
        if self.request.method in ["PATCH", "PUT"]:
            return TripWriteSerializer
        return TripDetailSerializer

    def get_queryset(self):
        return Trip.objects.select_related(
            "destination", "category", "expedition_detail"
        ).prefetch_related("itinerary_days", "departures", "reviews")

    @extend_schema(
        tags=["Trips"],
        responses={
            200: TripDetailSerializer,
            404: OpenApiResponse(description="Trip not found."),
        },
    )
    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        response.success_message = "Trip details retrieved successfully."
        return response

    @extend_schema(
        tags=["Trips Admin"],
        request=TripWriteSerializer,
        responses={
            200: TripDetailSerializer,
            400: OpenApiResponse(description="Validation error."),
            403: OpenApiResponse(description="Forbidden: Admin role required."),
            404: OpenApiResponse(description="Trip not found."),
        },
    )
    def patch(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        trip = serializer.save()
        output_serializer = TripDetailSerializer(trip)
        response = Response(output_serializer.data, status=status.HTTP_200_OK)
        response.success_message = "Trip updated successfully."
        return response

    @extend_schema(
        tags=["Trips Admin"],
        responses={
            204: OpenApiResponse(description="Trip deleted successfully."),
            403: OpenApiResponse(description="Forbidden: Admin role required."),
            404: OpenApiResponse(description="Trip not found."),
        },
    )
    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        response = Response(status=status.HTTP_204_NO_CONTENT)
        response.success_message = "Trip deleted successfully."
        return response
