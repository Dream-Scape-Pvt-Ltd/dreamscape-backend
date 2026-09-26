from django.db import transaction
from django.db.models import Avg, Count, Q
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import generics, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.lookups import SlugOrIdLookupMixin
from apps.common.models import MediaAsset
from apps.common.permissions import IsAdminRole
from apps.trips.filters import TripFilter
from apps.trips.models import Trip, ItineraryDay
from apps.trips.serializers import (
    TripDetailSerializer,
    TripListSerializer,
    TripImageUploadSerializer,
    TripWriteSerializer,
)


class TripImageUploadView(APIView):
    """Upload cover and gallery images for the admin trek editor."""

    permission_classes = [IsAdminRole]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(tags=["Trips Admin"], request=TripImageUploadSerializer)
    def post(self, request, *args, **kwargs):
        files = request.FILES.getlist("files")
        if not files:
            return Response(
                {"files": ["Select at least one image."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(files) > 12:
            return Response(
                {"files": ["Upload no more than 12 images at once."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        uploaded = []
        for image in files:
            serializer = TripImageUploadSerializer(data={"file": image})
            serializer.is_valid(raise_exception=True)
            valid_image = serializer.validated_data["file"]
            asset = MediaAsset.objects.create(
                file=valid_image,
                original_name=valid_image.name[:255],
                mime_type=valid_image.content_type,
                file_size_bytes=valid_image.size,
                uploaded_by=request.user,
            )
            uploaded.append(
                {
                    "id": str(asset.id),
                    "url": request.build_absolute_uri(asset.file.url),
                    "name": asset.original_name,
                    "size": asset.file_size_bytes,
                }
            )

        response = Response({"files": uploaded}, status=status.HTTP_201_CREATED)
        response.success_message = "Trek image upload completed."
        return response


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
        itinerary_data = request.data.get("itinerary_days", None)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            trip = serializer.save()
            if itinerary_data is not None and isinstance(itinerary_data, list):
                new_days = []
                for idx, day_info in enumerate(itinerary_data, start=1):
                    if not isinstance(day_info, dict):
                        continue
                    new_days.append(
                        ItineraryDay(
                            trip=trip,
                            day_number=day_info.get("day_number", idx),
                            title=day_info.get("title", f"Day {idx}"),
                            description=day_info.get("description", ""),
                            overnight_stay=day_info.get("overnight_stay", ""),
                            elevation_meters=day_info.get("elevation_meters") if day_info.get("elevation_meters") is not None and str(day_info.get("elevation_meters")).strip() != "" else None,
                            accommodation_type=day_info.get("accommodation_type") or "TEAHOUSE",
                            is_acclimatization_day=bool(day_info.get("is_acclimatization_day", False)),
                            meals_included=day_info.get("meals_included", []),
                            latitude=day_info.get("latitude") or None,
                            longitude=day_info.get("longitude") or None,
                        )
                    )
                if new_days:
                    ItineraryDay.objects.bulk_create(new_days)
        output_serializer = TripDetailSerializer(trip)
        response = Response(output_serializer.data, status=status.HTTP_201_CREATED)
        response.success_message = "Trip created successfully."
        return response


class TripDetailView(SlugOrIdLookupMixin, generics.RetrieveUpdateDestroyAPIView):
    """
    Complete trip details by slug or id, including itineraries, departures, reviews,
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
        ).prefetch_related("itinerary_days", "departures", "reviews", "trek_guides")

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
        itinerary_data = request.data.get("itinerary_days", None)
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            trip = serializer.save()
            if itinerary_data is not None and isinstance(itinerary_data, list):
                instance.itinerary_days.all().delete()
                new_days = []
                for idx, day_info in enumerate(itinerary_data, start=1):
                    if not isinstance(day_info, dict):
                        continue
                    new_days.append(
                        ItineraryDay(
                            trip=trip,
                            day_number=day_info.get("day_number", idx),
                            title=day_info.get("title", f"Day {idx}"),
                            description=day_info.get("description", ""),
                            overnight_stay=day_info.get("overnight_stay", ""),
                            elevation_meters=day_info.get("elevation_meters") if day_info.get("elevation_meters") is not None and str(day_info.get("elevation_meters")).strip() != "" else None,
                            accommodation_type=day_info.get("accommodation_type") or "TEAHOUSE",
                            is_acclimatization_day=bool(day_info.get("is_acclimatization_day", False)),
                            meals_included=day_info.get("meals_included", []),
                            latitude=day_info.get("latitude") or None,
                            longitude=day_info.get("longitude") or None,
                        )
                    )
                if new_days:
                    ItineraryDay.objects.bulk_create(new_days)
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
