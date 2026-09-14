from pathlib import Path
from urllib.parse import urlencode

from django.conf import settings
from django.core import signing
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from drf_spectacular.utils import extend_schema, OpenApiTypes, OpenApiParameter
from rest_framework import generics
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.response import Response

from apps.accounts.models import UserRole
from apps.b2b.models import B2BAsset
from apps.b2b.permissions import IsApprovedPartnerOrAdmin
from apps.b2b.serializers.asset_serializers import B2BAssetSerializer, B2BAssetDownloadSerializer, TIER_RANKS
from apps.common.exceptions import TierInsufficientError

SIGNING_SALT = 'b2b.private-asset'


@extend_schema(parameters=[OpenApiParameter('trip_slug', str)])
class B2BAssetListView(generics.ListAPIView):
    permission_classes = [IsApprovedPartnerOrAdmin]
    serializer_class = B2BAssetSerializer
    filterset_fields = ['asset_type']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return B2BAsset.objects.none()
        qs = B2BAsset.objects.filter(is_active=True).select_related('trip').order_by('-created_at', 'id')
        if self.request.user.role != UserRole.ADMIN:
            rank = TIER_RANKS[self.request.user.b2b_profile.agency_tier]
            qs = qs.filter(minimum_tier__in=[tier for tier, value in TIER_RANKS.items() if value <= rank])
        if self.request.query_params.get('trip_slug'):
            qs = qs.filter(trip__slug=self.request.query_params['trip_slug'])
        return qs


class B2BAssetDownloadView(generics.GenericAPIView):
    permission_classes = [IsApprovedPartnerOrAdmin]
    serializer_class = B2BAssetDownloadSerializer

    def get_asset(self, asset_id):
        asset = get_object_or_404(B2BAsset.objects.select_related('trip'), pk=asset_id, is_active=True)
        if self.request.user.role != UserRole.ADMIN:
            if TIER_RANKS[self.request.user.b2b_profile.agency_tier] < TIER_RANKS[asset.minimum_tier]:
                raise TierInsufficientError()
        if not asset.file:
            raise NotFound('Asset file is unavailable.')
        return asset

    def get(self, request, asset_id):
        asset = self.get_asset(asset_id)
        token = signing.dumps({'asset': str(asset.pk), 'user': str(request.user.pk), 'file': asset.file.name}, salt=SIGNING_SALT)
        path = reverse('b2b:asset-file', kwargs={'asset_id': asset.pk})
        response = Response({'download_url': request.build_absolute_uri(path) + '?' + urlencode({'token': token}),
                             'expires_in_seconds': settings.B2B_DOWNLOAD_TTL})
        response['Cache-Control'] = 'private, no-store'
        return response


class B2BAssetFileView(B2BAssetDownloadView):
    @extend_schema(responses={(200, 'application/octet-stream'): OpenApiTypes.BINARY},
                   parameters=[OpenApiParameter('token', str, required=True)])
    def get(self, request, asset_id):
        asset = self.get_asset(asset_id)
        try:
            payload = signing.loads(request.query_params.get('token', ''), salt=SIGNING_SALT,
                                    max_age=settings.B2B_DOWNLOAD_TTL)
        except signing.BadSignature:
            raise PermissionDenied('Download link is invalid or expired.')
        if payload != {'asset': str(asset.pk), 'user': str(request.user.pk), 'file': asset.file.name}:
            raise PermissionDenied('Download link does not belong to this account or asset.')
        try:
            stream = asset.file.open('rb')
        except FileNotFoundError:
            raise NotFound('Asset file is unavailable.')
        response = FileResponse(stream, as_attachment=True, filename=Path(asset.file.name).name,
                                content_type='application/octet-stream')
        response['Cache-Control'] = 'private, no-store'
        return response
