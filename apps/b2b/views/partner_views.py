from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.b2b.models import B2BPartner
from apps.b2b.permissions import IsPartner
from apps.b2b.serializers.partner_serializers import (
    B2BRegistrationSerializer, B2BRegistrationResponseSerializer, B2BPartnerProfileSerializer,
    B2BPartnerAdminSerializer, B2BPartnerApprovalSerializer,
)
from apps.b2b.tasks import queue_partner_email
from apps.common.permissions import IsAdminRole


class B2BRegisterView(generics.GenericAPIView):
    permission_classes = [AllowAny]

    def post(self, request):
        raise PermissionDenied(
            'Public agency registration is disabled. Please submit a wholesale partnership inquiry via /api/v1/inquiries/.'
        )


class B2BPartnerListView(generics.ListAPIView):
    permission_classes = [IsAdminRole]
    serializer_class = B2BPartnerAdminSerializer
    queryset = B2BPartner.objects.select_related('user').order_by('company_name', 'id')
    filterset_fields = ['approved', 'agency_tier', 'country']


class B2BPartnerMeView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsPartner]
    serializer_class = B2BPartnerProfileSerializer
    http_method_names = ['get', 'patch', 'head', 'options']

    def get_object(self):
        return get_object_or_404(B2BPartner.objects.select_related('user'), user=self.request.user)

    @transaction.atomic
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    def get_queryset(self):
        return B2BPartner.objects.select_related('user')

    def perform_update(self, serializer):
        # Reload under lock so a profile edit cannot overwrite an approval.
        partner = self.get_queryset().select_for_update(of=('self',)).get(pk=serializer.instance.pk)
        serializer.instance = partner
        serializer.save()


class B2BPartnerApproveView(generics.GenericAPIView):
    permission_classes = [IsAdminRole]
    serializer_class = B2BPartnerApprovalSerializer

    @extend_schema(responses=B2BPartnerProfileSerializer)
    @transaction.atomic
    def post(self, request, partner_id):
        partner = get_object_or_404(
            B2BPartner.objects.select_related('user').select_for_update(of=('self',)), pk=partner_id)
        was_approved = partner.approved
        serializer = self.get_serializer(partner, data=request.data)
        serializer.is_valid(raise_exception=True)
        partner = serializer.save()
        if partner.approved and not was_approved:
            queue_partner_email(partner.user.email, 'Your Dreamscape agency account is approved',
                                f'Your agency {partner.company_name} is approved at {partner.agency_tier} tier. '
                                'Sign in to access your partner portal.')
        return Response(B2BPartnerProfileSerializer(partner).data)
