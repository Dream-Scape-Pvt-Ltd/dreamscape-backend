from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import generics, status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.common.permissions import IsAdminRole
from apps.trips.models import ItineraryDay, Trip
from apps.trips.serializers import ItineraryDaySerializer


class ItineraryView(generics.ListCreateAPIView):
    """
    List all itinerary days for a specific trip, or add new days (Admin only).
    """

    serializer_class = ItineraryDaySerializer

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAdminRole()]
        return [AllowAny()]

    def get_trip(self):
        slug = self.kwargs.get("slug")
        trip = Trip.objects.filter(slug=slug).first()
        if not trip:
            raise NotFound(detail=f"Trip with slug '{slug}' not found.")
        return trip

    def get_queryset(self):
        trip = self.get_trip()
        return ItineraryDay.objects.filter(trip=trip).order_by("day_number")

    @extend_schema(
        tags=["Trips"],
        responses={200: ItineraryDaySerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        response.success_message = "Itinerary retrieved successfully."
        return response

    @extend_schema(
        tags=["Trips Admin"],
        request=ItineraryDaySerializer,
        responses={
            201: ItineraryDaySerializer,
            400: OpenApiResponse(description="Validation error."),
            403: OpenApiResponse(description="Forbidden: Admin role required."),
            404: OpenApiResponse(description="Trip not found."),
        },
    )
    def post(self, request, *args, **kwargs):
        trip = self.get_trip()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        itinerary_day = serializer.save(trip=trip)
        response = Response(self.get_serializer(itinerary_day).data, status=status.HTTP_201_CREATED)
        response.success_message = "Itinerary day created successfully."
        return response


class ItineraryDayDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete a specific itinerary day by day number.
    """

    serializer_class = ItineraryDaySerializer

    def get_permissions(self):
        if self.request.method in ["PATCH", "PUT", "DELETE"]:
            return [IsAdminRole()]
        return [AllowAny()]

    def get_object(self):
        slug = self.kwargs.get("slug")
        day_number = self.kwargs.get("day_number")
        try:
            return ItineraryDay.objects.get(trip__slug=slug, day_number=day_number)
        except ItineraryDay.DoesNotExist:
            raise NotFound(detail=f"Itinerary day {day_number} not found for trip '{slug}'.")

    @extend_schema(
        tags=["Trips"],
        responses={
            200: ItineraryDaySerializer,
            404: OpenApiResponse(description="Itinerary day not found."),
        },
    )
    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        response.success_message = "Itinerary day retrieved successfully."
        return response

    @extend_schema(
        tags=["Trips Admin"],
        request=ItineraryDaySerializer,
        responses={
            200: ItineraryDaySerializer,
            400: OpenApiResponse(description="Validation error."),
            403: OpenApiResponse(description="Forbidden: Admin role required."),
        },
    )
    def patch(self, request, *args, **kwargs):
        response = super().patch(request, *args, **kwargs)
        response.success_message = "Itinerary day updated successfully."
        return response

    @extend_schema(
        tags=["Trips Admin"],
        responses={
            204: OpenApiResponse(description="Itinerary day deleted successfully."),
            403: OpenApiResponse(description="Forbidden: Admin role required."),
        },
    )
    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        response = Response(status=status.HTTP_204_NO_CONTENT)
        response.success_message = "Itinerary day deleted successfully."
        return response
