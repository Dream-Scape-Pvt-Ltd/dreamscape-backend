from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes
from rest_framework import generics, serializers
from rest_framework.response import Response

from apps.accounts.models import UserRole
from apps.b2b.models import B2BBooking
from apps.b2b.permissions import IsApprovedPartnerOrAdmin
from apps.b2b.serializers.booking_serializers import B2BBookingSerializer, B2BCommissionUpdateSerializer
from apps.common.permissions import IsAdminRole


def ledger_queryset():
    return B2BBooking.objects.select_related('partner__user', 'booking__departure__trip', 'booking__custom_trip')


@extend_schema(parameters=[OpenApiParameter('from_date', OpenApiTypes.DATE)])
class B2BBookingListView(generics.ListAPIView):
    permission_classes = [IsApprovedPartnerOrAdmin]
    serializer_class = B2BBookingSerializer
    filterset_fields = ['commission_status']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return B2BBooking.objects.none()
        qs = ledger_queryset().order_by('-created_at', 'id')
        if self.request.user.role != UserRole.ADMIN:
            qs = qs.filter(partner__user=self.request.user)
        if 'from_date' in self.request.query_params:
            date = serializers.DateField().run_validation(self.request.query_params['from_date'])
            qs = qs.filter(booking__trip_start_date__gte=date)
        return qs


class B2BCommissionUpdateView(generics.GenericAPIView):
    permission_classes = [IsAdminRole]
    serializer_class = B2BCommissionUpdateSerializer

    @extend_schema(responses=B2BBookingSerializer)
    @transaction.atomic
    def patch(self, request, b2b_booking_id):
        ledger = get_object_or_404(ledger_queryset().select_for_update(of=('self',)), pk=b2b_booking_id)
        serializer = self.get_serializer(ledger, data=request.data)
        serializer.is_valid(raise_exception=True)
        ledger = serializer.save()
        return Response(B2BBookingSerializer(ledger).data)
