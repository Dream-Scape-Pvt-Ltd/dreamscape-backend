from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import IsAdminRole, IsSalesAgentOrAdmin
from apps.inquiries.models import LeadAssignmentRule
from apps.inquiries.serializers.assignment_serializers import (
    BulkAssignSerializer,
    LeadAssignmentRuleSerializer,
    LeadAssignmentRuleWriteSerializer,
)
from apps.trips.filters import DepartureCapacityFilter
from apps.trips.models import TripDeparture
from apps.trips.serializers import DepartureCapacitySerializer


class LeadAssignmentRuleListCreateView(generics.ListCreateAPIView):
    """
    GET/POST /api/v1/inquiries/crm/assignment-rules/
        Manage the tour -> agent routing table.
        Permissions: IsAdminRole.
    """

    permission_classes = [IsAdminRole]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return LeadAssignmentRuleWriteSerializer
        return LeadAssignmentRuleSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return LeadAssignmentRule.objects.none()
        return (
            LeadAssignmentRule.objects.all()
            .select_related("agent", "trip", "destination", "departure__trip")
            .order_by("-priority", "created_at")
        )

    @extend_schema(tags=["CRM Admin"], responses={200: LeadAssignmentRuleSerializer(many=True)})
    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        response.success_message = "Assignment rules retrieved successfully."
        return response

    @extend_schema(
        tags=["CRM Admin"],
        request=LeadAssignmentRuleWriteSerializer,
        responses={
            201: LeadAssignmentRuleSerializer,
            400: OpenApiResponse(description="Validation error."),
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rule = serializer.save()
        response = Response(
            LeadAssignmentRuleSerializer(rule).data, status=status.HTTP_201_CREATED
        )
        response.success_message = "Assignment rule created successfully."
        return response


class LeadAssignmentRuleDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET/PATCH/DELETE /api/v1/inquiries/crm/assignment-rules/<uuid:pk>/
        Permissions: IsAdminRole.
    """

    permission_classes = [IsAdminRole]
    queryset = LeadAssignmentRule.objects.select_related(
        "agent", "trip", "destination", "departure__trip"
    )

    def get_serializer_class(self):
        if self.request.method in ["PATCH", "PUT"]:
            return LeadAssignmentRuleWriteSerializer
        return LeadAssignmentRuleSerializer

    @extend_schema(tags=["CRM Admin"], responses={200: LeadAssignmentRuleSerializer})
    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        response.success_message = "Assignment rule retrieved successfully."
        return response

    @extend_schema(
        tags=["CRM Admin"],
        request=LeadAssignmentRuleWriteSerializer,
        responses={200: LeadAssignmentRuleSerializer},
    )
    def patch(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        rule = serializer.save()
        response = Response(LeadAssignmentRuleSerializer(rule).data, status=status.HTTP_200_OK)
        response.success_message = "Assignment rule updated successfully."
        return response

    @extend_schema(tags=["CRM Admin"], responses={204: OpenApiResponse(description="Deleted.")})
    def delete(self, request, *args, **kwargs):
        response = super().delete(request, *args, **kwargs)
        response.success_message = "Assignment rule deleted successfully."
        return response


class BulkAssignView(APIView):
    """
    POST /api/v1/inquiries/bulk-assign/
        Reassign a set of leads — an explicit list, or a whole tour/departure
        batch — to one agent.
        Permissions: IsAdminRole (reassigning another agent's leads is an
        administrative action).
    """

    permission_classes = [IsAdminRole]

    @extend_schema(
        tags=["CRM Admin"],
        request=BulkAssignSerializer,
        responses={
            200: OpenApiResponse(description="Leads reassigned."),
            400: OpenApiResponse(description="Validation error."),
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = BulkAssignSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        result = serializer.assign()

        response = Response(result, status=status.HTTP_200_OK)
        response.success_message = (
            f"{result['reassigned']} of {result['matched']} matched lead(s) reassigned."
        )
        return response


class LeadsByDepartureView(generics.ListAPIView):
    """
    GET /api/v1/inquiries/crm/by-departure/
        Departure-grouped CRM board: the seat ledger for each batch alongside
        its open lead count, waitlist depth, and capacity state.
        Permissions: IsSalesAgentOrAdmin.

        Filters: ?trip=, ?destination=, ?status=, ?start_after=, ?start_before=,
        ?capacity_state=
    """

    permission_classes = [IsSalesAgentOrAdmin]
    serializer_class = DepartureCapacitySerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = DepartureCapacityFilter

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return TripDeparture.objects.none()
        return (
            TripDeparture.objects.with_capacity_counts()
            .select_related("trip")
            .order_by("start_date")
        )

    @extend_schema(
        tags=["CRM"],
        responses={200: DepartureCapacitySerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        response.success_message = "Departure lead board retrieved successfully."
        return response
