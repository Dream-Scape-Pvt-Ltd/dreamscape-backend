from django.db.models import Q
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.common.permissions import IsSalesAgentOrAdmin
from apps.common.throttling import InquiryThrottle, WriteThrottleMixin
from apps.inquiries.filters import InquiryFilter
from apps.inquiries.models import Inquiry, InquiryNote
from apps.inquiries.serializers import (
    InquiryCreateSerializer,
    InquiryDetailSerializer,
    InquiryListSerializer,
    InquiryNoteSerializer,
    InquiryUpdateSerializer,
)


class InquiryListCreateView(WriteThrottleMixin, generics.ListCreateAPIView):
    """
    POST /api/v1/inquiries/
        Public inbound lead capture form (General, Journey, or Tailor-Made trip inquiries).
        Permissions: AllowAny.

    GET /api/v1/inquiries/
        CRM Lead pipeline dashboard list.
        Permissions: IsSalesAgentOrAdmin (restricted to SALES_AGENT and ADMIN roles).
        Filters: see InquiryFilter — ?trip= (slug), ?departure= (uuid), ?status=,
        ?inquiry_type=, ?assigned_agent= (UUID, 'me' or 'unassigned'),
        ?lead_source=, ?sla_breached=, ?tag=, ?created_after=/?created_before=,
        ?departure_after=/?departure_before=, ?search=
    """

    filter_backends = [DjangoFilterBackend]
    filterset_class = InquiryFilter
    write_throttle_classes = (InquiryThrottle,)

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

        # Filtering is handled by InquiryFilter (filterset_class) so that bad
        # input is rejected with 400 rather than reaching the database.
        return (
            Inquiry.objects.all()
            .select_related("assigned_agent", "trip", "trip__destination", "departure__trip")
            .prefetch_related("tags")
            .order_by("-created_at")
            .distinct()
        )

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
