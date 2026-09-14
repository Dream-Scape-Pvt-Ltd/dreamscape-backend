from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import IsAdminRole
from apps.trips.models import PeakExpeditionDetail, Trip
from apps.trips.serializers import PeakExpeditionDetailSerializer


class ExpeditionDetailView(APIView):
    """
    Mountaineering expedition technical specifications, summit window, and gear requirements.
    Admins can create or update expedition details.
    """

    def get_permissions(self):
        if self.request.method in ["POST", "PATCH", "PUT"]:
            return [IsAdminRole()]
        return [AllowAny()]

    def get_trip(self, slug):
        trip = Trip.objects.filter(slug=slug).first()
        if not trip:
            raise NotFound(detail=f"Trip with slug '{slug}' not found.")
        return trip

    @extend_schema(
        tags=["Trips"],
        responses={
            200: PeakExpeditionDetailSerializer,
            404: OpenApiResponse(description="Expedition details not found."),
        },
    )
    def get(self, request, slug):
        trip = self.get_trip(slug)
        if not hasattr(trip, "expedition_detail"):
            raise NotFound(detail=f"No expedition details exist for trip '{slug}'.")
        serializer = PeakExpeditionDetailSerializer(trip.expedition_detail)
        response = Response(serializer.data, status=status.HTTP_200_OK)
        response.success_message = "Expedition details retrieved successfully."
        return response

    @extend_schema(
        tags=["Trips Admin"],
        request=PeakExpeditionDetailSerializer,
        responses={
            200: PeakExpeditionDetailSerializer,
            201: PeakExpeditionDetailSerializer,
            400: OpenApiResponse(description="Validation error."),
            403: OpenApiResponse(description="Forbidden: Admin role required."),
        },
    )
    def post(self, request, slug):
        trip = self.get_trip(slug)
        instance = getattr(trip, "expedition_detail", None)
        status_code = status.HTTP_200_OK if instance else status.HTTP_201_CREATED

        serializer = PeakExpeditionDetailSerializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        expedition_detail = serializer.save(trip=trip)

        response = Response(PeakExpeditionDetailSerializer(expedition_detail).data, status=status_code)
        response.success_message = "Expedition details saved successfully."
        return response

    @extend_schema(
        tags=["Trips Admin"],
        request=PeakExpeditionDetailSerializer,
        responses={
            200: PeakExpeditionDetailSerializer,
            400: OpenApiResponse(description="Validation error."),
            403: OpenApiResponse(description="Forbidden: Admin role required."),
        },
    )
    def patch(self, request, slug):
        return self.post(request, slug)
