from django.db import transaction
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import IsAdminRole
from apps.trips.models import Trip
from apps.trips.serializers import TripListSerializer
from apps.trips.serializers.trip_serializers import TripHighlightUpdateSerializer


class TripHighlightView(APIView):
    """
    Endpoint for managing and retrieving highlighted treks and tours.
    - Public GET: Returns up to 5 curated highlighted trips. Falls back to featured trips
      if no trips are currently flagged as highlighted.
    - Admin PUT / POST: Atomically replaces the current highlighted selection with up to 5
      specified trips in exact display order.
    """

    def get_permissions(self):
        if self.request.method in ["PUT", "POST"]:
            return [IsAdminRole()]
        return [AllowAny()]

    @extend_schema(
        tags=["Trips"],
        summary="Get highlighted treks/tours",
        description=(
            "Returns up to 5 curated highlight treks/tours for the homepage and promotional sections. "
            "If no trips have been explicitly curated as highlights, automatically falls back to "
            "top featured trips."
        ),
        responses={200: TripListSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        qs = (
            Trip.objects.filter(is_active=True, is_highlighted=True)
            .select_related("destination", "category")
            .order_by("highlight_order", "title")[:5]
        )
        trips = list(qs)

        # Fallback to featured trips if no highlights are configured
        if not trips:
            fallback_qs = (
                Trip.objects.filter(is_active=True, is_featured=True)
                .select_related("destination", "category")
                .order_by("title")[:5]
            )
            trips = list(fallback_qs)

        serializer = TripListSerializer(trips, many=True)
        response = Response(serializer.data, status=status.HTTP_200_OK)
        response.success_message = "Highlighted trips retrieved successfully."
        return response

    @extend_schema(
        tags=["Trips Admin"],
        summary="Update highlighted treks/tours (up to 5)",
        description=(
            "Admin-only endpoint to curate up to 5 highlighted treks/tours by providing an ordered list "
            "of trip IDs or slugs. Atomically replaces all existing highlights and sets their display order."
        ),
        request=TripHighlightUpdateSerializer,
        responses={
            200: TripListSerializer(many=True),
            400: OpenApiResponse(
                description="Validation error (e.g. more than 5 trips, duplicates, or invalid trip identifiers)."
            ),
            401: OpenApiResponse(description="Unauthorized: Missing or invalid authentication token."),
            403: OpenApiResponse(description="Forbidden: Admin role required."),
        },
    )
    def put(self, request, *args, **kwargs):
        serializer = TripHighlightUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        ordered_trips = serializer.validated_data["_resolved_trips"]

        with transaction.atomic():
            # Reset all current highlights
            Trip.objects.filter(is_highlighted=True).update(
                is_highlighted=False,
                highlight_order=None,
            )

            # Assign new highlights with ordered positions (1..5)
            updated_trips = []
            for order_idx, trip in enumerate(ordered_trips, start=1):
                trip.is_highlighted = True
                trip.highlight_order = order_idx
                trip.save(update_fields=["is_highlighted", "highlight_order"])
                updated_trips.append(trip)

        output_serializer = TripListSerializer(updated_trips, many=True)
        response = Response(output_serializer.data, status=status.HTTP_200_OK)
        response.success_message = "Highlighted trips updated successfully."
        return response

    @extend_schema(
        tags=["Trips Admin"],
        summary="Update highlighted treks/tours (up to 5)",
        description="Alias for PUT /api/v1/trips/highlights/ to allow POST curation payload.",
        request=TripHighlightUpdateSerializer,
        responses={
            200: TripListSerializer(many=True),
            400: OpenApiResponse(description="Validation error."),
            401: OpenApiResponse(description="Unauthorized."),
            403: OpenApiResponse(description="Forbidden: Admin role required."),
        },
    )
    def post(self, request, *args, **kwargs):
        return self.put(request, *args, **kwargs)
