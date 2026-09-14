from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.bookings.models import Booking, PassengerDetail
from apps.bookings.serializers import PassengerDetailSerializer
from apps.common.permissions import IsOwnerOrAdmin


class PassengerListView(generics.ListAPIView):
    """
    GET /api/v1/bookings/{booking_reference}/passengers/
        Retrieve manifest of all registered passengers for a specific booking.
        Permissions: IsAuthenticated + IsOwnerOrAdmin (on parent booking).
    """

    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    serializer_class = PassengerDetailSerializer

    def get_booking(self):
        booking_ref = self.kwargs.get("booking_reference")
        booking = get_object_or_404(
            Booking.objects.select_related("customer_user"),
            booking_reference=booking_ref,
        )
        self.check_object_permissions(self.request, booking)
        return booking

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return PassengerDetail.objects.none()
        booking = self.get_booking()
        return PassengerDetail.objects.filter(booking=booking).order_by("created_at")


class PassengerDetailView(generics.RetrieveUpdateAPIView):
    """
    GET /api/v1/bookings/{booking_reference}/passengers/{passenger_id}/
    PATCH /api/v1/bookings/{booking_reference}/passengers/{passenger_id}/
        Retrieve or partially update passenger details (passport, medical, insurance).
        Enforces minimum 6 months passport validity beyond trip start date on update.
        Permissions: IsAuthenticated + IsOwnerOrAdmin (on passenger or parent booking).
    """

    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    serializer_class = PassengerDetailSerializer
    lookup_field = "id"
    lookup_url_kwarg = "passenger_id"

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return PassengerDetail.objects.none()
        booking_ref = self.kwargs.get("booking_reference")
        return PassengerDetail.objects.filter(
            booking__booking_reference=booking_ref
        ).select_related("booking__departure")

    def get_object(self):
        if hasattr(self, "_cached_object"):
            return self._cached_object
        obj = super().get_object()
        self._cached_object = obj
        return obj

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if getattr(self, "swagger_fake_view", False):
            return context
        if self.kwargs.get("passenger_id"):
            try:
                passenger = self.get_object()
                context["booking"] = passenger.booking
                if passenger.booking and passenger.booking.trip_start_date:
                    context["trip_start_date"] = passenger.booking.trip_start_date
            except Exception:
                pass
        return context
