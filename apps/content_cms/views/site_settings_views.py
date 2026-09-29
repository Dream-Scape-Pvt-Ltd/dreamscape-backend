import json

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.exceptions import _build_error_envelope
from apps.content_cms.models import SiteSettings
from apps.content_cms.views.permissions import IsAdminOrReadOnly, is_editor

MAX_CONTENT_BYTES = 400_000


def _error(message):
    return Response(_build_error_envelope(code="VALIDATION_ERROR", message=message, details=None), status=status.HTTP_400_BAD_REQUEST)


class SiteSettingsView(APIView):
    """
    GET is public (website copy, menus, contact details); editors also receive
    `crm_sla_hours`. PATCH replaces the content object and, if sent, the SLA hours.
    """

    permission_classes = [IsAdminOrReadOnly]

    def get_throttles(self):
        # Every page render reads this (cached by the frontend); only writes count against the rate limit.
        return [] if self.request.method == "GET" else super().get_throttles()

    def _payload(self, request, row):
        data = dict(row.content)
        if is_editor(request.user):
            data["crm_sla_hours"] = row.crm_sla_hours
        return data

    @extend_schema(tags=["Site settings"], responses={200: OpenApiResponse(description="Site settings.")})
    def get(self, request):
        row = SiteSettings.objects.filter().first() or SiteSettings(content={})
        response = Response(self._payload(request, row))
        response.success_message = "Site settings retrieved successfully."
        return response

    @extend_schema(tags=["Site settings"], responses={200: OpenApiResponse(description="Site settings saved."), 400: OpenApiResponse(description="Invalid settings.")})
    def patch(self, request):
        if not isinstance(request.data, dict):
            return _error("Settings must be a JSON object.")
        content = dict(request.data)
        row = SiteSettings.load()
        if "crm_sla_hours" in content:
            hours = content.pop("crm_sla_hours")
            if hours is not None and (isinstance(hours, bool) or not isinstance(hours, int) or not 1 <= hours <= 168):
                return _error("Response time must be a whole number of hours between 1 and 168.")
            row.crm_sla_hours = hours
        if len(json.dumps(content)) > MAX_CONTENT_BYTES:
            return _error("The settings are too large to save.")
        row.content = content
        row.save()
        response = Response(self._payload(request, row))
        response.success_message = "Site settings saved."
        return response
