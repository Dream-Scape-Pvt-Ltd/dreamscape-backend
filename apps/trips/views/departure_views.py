from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import generics, status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.common.permissions import IsAdminRole
from apps.trips.models import DepartureStatus, Trip, TripDeparture
from apps.trips.serializers import (
    TripDepartureSerializer,
    TripDepartureWriteSerializer,
)


class DepartureListCreateView(generics.ListCreateAPIView):
    """
    List scheduled departure dates and seat availability for a trip.
    Admins can schedule new departures.
    """

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAdminRole()]
        return [AllowAny()]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return TripDepartureWriteSerializer
        return TripDepartureSerializer

    def get_trip(self):
        slug = self.kwargs.get("slug")
        trip = Trip.objects.filter(slug=slug).first()
        if not trip:
            raise NotFound(detail=f"Trip with slug '{slug}' not found.")
        return trip

    def get_queryset(self):
        trip = self.get_trip()
        qs = TripDeparture.objects.filter(trip=trip).order_by("start_date")

        # Optional query param: ?available_only=true
        if self.request.query_params.get("available_only", "").lower() in ["true", "1"]:
            qs = qs.filter(available_seats__gt=0).exclude(status=DepartureStatus.SOLD_OUT)

        return qs

    @extend_schema(
        tags=["Trips"],
        responses={200: TripDepartureSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        response.success_message = "Departures retrieved successfully."
        return response

    @extend_schema(
        tags=["Trips Admin"],
        request=TripDepartureWriteSerializer,
        responses={
            201: TripDepartureSerializer,
            400: OpenApiResponse(description="Validation error."),
            403: OpenApiResponse(description="Forbidden: Admin role required."),
            404: OpenApiResponse(description="Trip not found."),
        },
    )
    def post(self, request, *args, **kwargs):
        trip = self.get_trip()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        departure = serializer.save(trip=trip)
        response = Response(TripDepartureSerializer(departure).data, status=status.HTTP_201_CREATED)
        response.success_message = "Departure scheduled successfully."
        return response


class DepartureDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or cancel/delete a specific departure date.
    """

    lookup_url_kwarg = "departure_id"

    def get_permissions(self):
        if self.request.method in ["PATCH", "PUT", "DELETE"]:
            return [IsAdminRole()]
        return [AllowAny()]

    def get_serializer_class(self):
        if self.request.method in ["PATCH", "PUT"]:
            return TripDepartureWriteSerializer
        return TripDepartureSerializer

    def get_object(self):
        slug = self.kwargs.get("slug")
        dep_id = self.kwargs.get("departure_id")
        try:
            return TripDeparture.objects.get(trip__slug=slug, pk=dep_id)
        except TripDeparture.DoesNotExist:
            raise NotFound(detail=f"Departure '{dep_id}' not found for trip '{slug}'.")

    @extend_schema(
        tags=["Trips"],
        responses={
            200: TripDepartureSerializer,
            404: OpenApiResponse(description="Departure not found."),
        },
    )
    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        response.success_message = "Departure retrieved successfully."
        return response

    @extend_schema(
        tags=["Trips Admin"],
        request=TripDepartureWriteSerializer,
        responses={
            200: TripDepartureSerializer,
            400: OpenApiResponse(description="Validation error."),
            403: OpenApiResponse(description="Forbidden: Admin role required."),
            404: OpenApiResponse(description="Departure not found."),
        },
    )
    def patch(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        departure = serializer.save()
        response = Response(TripDepartureSerializer(departure).data, status=status.HTTP_200_OK)
        response.success_message = "Departure updated successfully."
        return response

    @extend_schema(
        tags=["Trips Admin"],
        responses={
            204: OpenApiResponse(description="Departure deleted successfully."),
            403: OpenApiResponse(description="Forbidden: Admin role required."),
            404: OpenApiResponse(description="Departure not found."),
        },
    )
    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        response = Response(status=status.HTTP_204_NO_CONTENT)
        response.success_message = "Departure deleted successfully."
        return response
