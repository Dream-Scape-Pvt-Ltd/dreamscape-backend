from django.db.models import Q
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import UserRole
from apps.bookings.models import Booking
from apps.bookings.serializers import (
    BookingCancelSerializer,
    BookingCreateSerializer,
    BookingDetailSerializer,
    BookingListSerializer,
)
from apps.bookings.tasks import send_booking_confirmation_email
from apps.common.permissions import IsOwnerOrAdmin


class BookingListCreateView(generics.ListCreateAPIView):
    """
    POST /api/v1/bookings/
        Initiate a booking checkout with atomic seat locking and split-payment calculation.
        Permissions: AllowAny (unauthenticated guests may book; if authenticated, links customer_user).

    GET /api/v1/bookings/
        List bookings.
        Permissions: IsAuthenticated.
        Customers see only their own bookings; Admins and Sales Agents see all bookings.
    """

    def get_permissions(self):
        if self.request.method == "POST":
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return BookingCreateSerializer
        return BookingListSerializer

    def get_queryset(self):
        user = self.request.user
        qs = (
            Booking.objects.all()
            .select_related("departure__trip", "custom_trip", "customer_user")
            .order_by("-created_at")
        )
        if user.role in (UserRole.ADMIN, UserRole.SALES_AGENT):
            return qs
        # Filter normal customer to their own bookings
        return qs.filter(
            Q(customer_user=user) | Q(customer_email__iexact=user.email)
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        booking = serializer.save()

        # Trigger async confirmation email notification
        try:
            send_booking_confirmation_email(booking.id)
        except Exception:
            pass

        # Return full detail representation
        detail_serializer = BookingDetailSerializer(booking, context={"request": request})
        return Response(detail_serializer.data, status=status.HTTP_201_CREATED)


class BookingDetailView(generics.RetrieveAPIView):
    """
    GET /api/v1/bookings/{booking_reference}/
        Retrieve full booking details including departure, passengers, and split-payment status.
        Permissions: IsAuthenticated + IsOwnerOrAdmin.
    """

    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    serializer_class = BookingDetailSerializer
    lookup_field = "booking_reference"
    lookup_url_kwarg = "booking_reference"

    def get_queryset(self):
        return (
            Booking.objects.all()
            .select_related("departure__trip", "custom_trip", "customer_user")
            .prefetch_related("passengers")
        )


class BookingCancelView(generics.GenericAPIView):
    """
    PATCH /api/v1/bookings/{booking_reference}/cancel/
        Cancel a booking and atomically restore departure available seats.
        Permissions: IsAuthenticated + IsOwnerOrAdmin.
    """

    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    serializer_class = BookingCancelSerializer
    lookup_field = "booking_reference"
    lookup_url_kwarg = "booking_reference"

    def get_queryset(self):
        return Booking.objects.select_related("departure", "customer_user")

    def patch(self, request, *args, **kwargs):
        booking = self.get_object()
        serializer = self.get_serializer(
            data=request.data,
            context={"booking": booking, "request": request},
        )
        serializer.is_valid(raise_exception=True)
        cancelled_booking = serializer.cancel_booking()

        detail_serializer = BookingDetailSerializer(cancelled_booking, context={"request": request})
        return Response(detail_serializer.data, status=status.HTTP_200_OK)
