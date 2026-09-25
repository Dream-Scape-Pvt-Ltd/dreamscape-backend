from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import IsAdminRole, IsSalesAgentOrAdmin
from apps.inquiries.models import RevenueEntry
from apps.inquiries.serializers import RevenueEntrySerializer
from apps.inquiries.services.revenue import revenue_summary


class RevenueAnalyticsView(APIView):
    """
    GET /api/v1/inquiries/crm/revenue/?months=6|12
        Revenue earned from completed treks plus manual entries: totals, a
        monthly series (including empty months), destination and trek
        breakdowns, and the latest revenue events.
        Permissions: IsSalesAgentOrAdmin.
    """

    permission_classes = [IsSalesAgentOrAdmin]

    def get(self, request, *args, **kwargs):
        months = request.query_params.get("months", "6")
        if months not in ("6", "12"):
            raise ValidationError({"months": "Choose 6 or 12 months."})
        return Response(revenue_summary(int(months)), status=status.HTTP_200_OK)


class RevenueEntryListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/v1/inquiries/crm/revenue-entries/  — manual revenue, newest first (staff).
    POST /api/v1/inquiries/crm/revenue-entries/  — record revenue by hand (admin only).
    """

    serializer_class = RevenueEntrySerializer
    queryset = RevenueEntry.objects.select_related("trip", "created_by")

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAdminRole()]
        return [IsSalesAgentOrAdmin()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class RevenueEntryDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET/PATCH/DELETE /api/v1/inquiries/crm/revenue-entries/{id}/
        Correct or remove a manual revenue entry. Permissions: IsAdminRole.
    """

    permission_classes = [IsAdminRole]
    serializer_class = RevenueEntrySerializer
    queryset = RevenueEntry.objects.select_related("trip", "created_by")
