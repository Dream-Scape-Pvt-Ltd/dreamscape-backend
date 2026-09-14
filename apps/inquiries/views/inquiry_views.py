from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.common.permissions import IsSalesAgentOrAdmin
from apps.inquiries.models import Inquiry, InquiryNote
from apps.inquiries.serializers import (
    InquiryCreateSerializer,
    InquiryDetailSerializer,
    InquiryListSerializer,
    InquiryNoteSerializer,
    InquiryUpdateSerializer,
)


class InquiryListCreateView(generics.ListCreateAPIView):
    """
    POST /api/v1/inquiries/
        Public inbound lead capture form (General, Journey, or Tailor-Made trip inquiries).
        Permissions: AllowAny.

    GET /api/v1/inquiries/
        CRM Lead pipeline dashboard list.
        Permissions: IsSalesAgentOrAdmin (restricted to SALES_AGENT and ADMIN roles).
        Filters: ?status=, ?inquiry_type=, ?assigned_agent= (UUID or 'me'), ?search=
    """

    def get_permissions(self):
        if self.request.method == "POST":
            return [AllowAny()]
        return [IsSalesAgentOrAdmin()]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return InquiryCreateSerializer
        return InquiryListSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Inquiry.objects.none()

        qs = (
            Inquiry.objects.all()
            .select_related("assigned_agent", "trip", "departure")
            .order_by("-created_at")
        )

        params = self.request.query_params
        # Filter by status
        status_filter = params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter.upper())

        # Filter by inquiry_type
        type_filter = params.get("inquiry_type")
        if type_filter:
            qs = qs.filter(inquiry_type=type_filter.upper())

        # Filter by assigned_agent
        agent_filter = params.get("assigned_agent")
        if agent_filter:
            if agent_filter.lower() == "me":
                qs = qs.filter(assigned_agent=self.request.user)
            else:
                qs = qs.filter(assigned_agent_id=agent_filter)

        # Search query across full_name, email, inquiry_number
        search_query = params.get("search")
        if search_query:
            qs = qs.filter(
                Q(full_name__icontains=search_query)
                | Q(email__icontains=search_query)
                | Q(inquiry_number__icontains=search_query)
            )

        return qs

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        inquiry = serializer.save()

        detail_serializer = InquiryDetailSerializer(inquiry, context={"request": request})
        return Response(detail_serializer.data, status=status.HTTP_201_CREATED)


class InquiryDetailUpdateView(generics.RetrieveUpdateAPIView):
    """
    GET /api/v1/inquiries/{inquiry_number}/
        Retrieve complete CRM lead details, trip specifications, tailor-made parameters, and note thread.
        Permissions: IsSalesAgentOrAdmin.

    PATCH /api/v1/inquiries/{inquiry_number}/
        Update lead status lifecycle (NEW -> ASSIGNED -> IN_CONTACT -> TRAVELING -> COMPLETED / CLOSED)
        or assign to a sales agent.
        Permissions: IsSalesAgentOrAdmin.
    """

    permission_classes = [IsSalesAgentOrAdmin]
    lookup_field = "inquiry_number"
    lookup_url_kwarg = "inquiry_number"

    def get_serializer_class(self):
        if self.request.method in ["PATCH", "PUT"]:
            return InquiryUpdateSerializer
        return InquiryDetailSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Inquiry.objects.none()

        return (
            Inquiry.objects.all()
            .select_related("assigned_agent", "trip", "departure")
            .prefetch_related("tailor_made_detail", "notes__author")
        )

    def patch(self, request, *args, **kwargs):
        inquiry = self.get_object()
        serializer = self.get_serializer(inquiry, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        updated_inquiry = serializer.save()

        detail_serializer = InquiryDetailSerializer(updated_inquiry, context={"request": request})
        return Response(detail_serializer.data, status=status.HTTP_200_OK)


class InquiryNoteListCreateView(generics.ListCreateAPIView):
    """
    GET /api/v1/inquiries/{inquiry_number}/notes/
        List internal communication logs and consultation notes attached to the lead.
        Permissions: IsSalesAgentOrAdmin.

    POST /api/v1/inquiries/{inquiry_number}/notes/
        Create an internal note authored by the requesting sales agent.
        Permissions: IsSalesAgentOrAdmin.
    """

    permission_classes = [IsSalesAgentOrAdmin]
    serializer_class = InquiryNoteSerializer

    def get_inquiry(self):
        inq_num = self.kwargs.get("inquiry_number")
        return get_object_or_404(Inquiry, inquiry_number=inq_num)

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return InquiryNote.objects.none()

        inquiry = self.get_inquiry()
        return (
            InquiryNote.objects.filter(inquiry=inquiry)
            .select_related("author")
            .order_by("-created_at")
        )

    def perform_create(self, serializer):
        inquiry = self.get_inquiry()
        serializer.save(inquiry=inquiry, author=self.request.user)
