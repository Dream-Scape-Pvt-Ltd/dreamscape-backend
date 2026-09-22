from django.db import transaction
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.bookings.models import DepartureWaitlistEntry, WaitlistStatus
from apps.bookings.serializers import WaitlistEntrySerializer, WaitlistJoinSerializer
from apps.bookings.services import promote_waitlist
from apps.common.permissions import IsAdminRole
from apps.trips.models import TripDeparture


class WaitlistJoinView(generics.CreateAPIView):
    """
    POST /api/v1/bookings/waitlist/
        Join the waitlist for a full departure.
        Permissions: AllowAny (mirrors guest checkout).
    """

    permission_classes = [AllowAny]
    serializer_class = WaitlistJoinSerializer

    @extend_schema(
        tags=["Bookings"],
        request=WaitlistJoinSerializer,
        responses={
            201: WaitlistEntrySerializer,
            400: OpenApiResponse(description="Validation error."),
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        entry = serializer.save()

        response = Response(
            WaitlistEntrySerializer(entry).data,
            status=status.HTTP_201_CREATED,
        )
        response.success_message = (
            f"You are number {entry.position} on the waitlist. "
            f"We will email you the moment a seat opens up."
        )
        return response


class DepartureWaitlistView(generics.ListAPIView):
    """
    GET /api/v1/bookings/waitlist/departures/<departure_id>/
        Admin view of a departure's waitlist queue, in position order.
        Permissions: IsAdminRole.
    """

    permission_classes = [IsAdminRole]
    serializer_class = WaitlistEntrySerializer
    pagination_class = None

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return DepartureWaitlistEntry.objects.none()
        return (
            DepartureWaitlistEntry.objects.filter(
                departure_id=self.kwargs["departure_id"]
            )
            .select_related("departure__trip")
            .order_by("position")
        )

    @extend_schema(
        tags=["Bookings Admin"],
        responses={200: WaitlistEntrySerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        response.success_message = "Waitlist retrieved successfully."
        return response


class WaitlistPromoteView(APIView):
    """
    POST /api/v1/bookings/waitlist/departures/<departure_id>/promote/
        Offer currently free seats to the head of the queue.
        Permissions: IsAdminRole.
    """

    permission_classes = [IsAdminRole]

    @extend_schema(
        tags=["Bookings Admin"],
        request=None,
        responses={
            200: WaitlistEntrySerializer(many=True),
            404: OpenApiResponse(description="Departure not found."),
        },
    )
    def post(self, request, departure_id, *args, **kwargs):
        with transaction.atomic():
            departure = (
                TripDeparture.objects.select_for_update()
                .filter(id=departure_id)
                .first()
            )
            if not departure:
                return Response(
                    {"detail": f"Departure '{departure_id}' not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            promoted = promote_waitlist(departure)

        response = Response(
            WaitlistEntrySerializer(promoted, many=True).data,
            status=status.HTTP_200_OK,
        )
        response.success_message = (
            f"{len(promoted)} waitlist entr{'y' if len(promoted) == 1 else 'ies'} offered a seat."
            if promoted
            else "No seats are free to offer right now."
        )
        return response
