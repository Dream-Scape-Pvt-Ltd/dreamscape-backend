from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import IsSalesAgentOrAdmin
from apps.inquiries.models import Activity, Inquiry, InquiryNote
from apps.inquiries.serializers import ActivityCreateSerializer, ActivitySerializer, InquiryNoteSerializer


def _get_inquiry(inquiry_number):
    return get_object_or_404(Inquiry, inquiry_number=inquiry_number)


class InquiryTimelineView(APIView):
    """
    GET /api/v1/inquiries/{inquiry_number}/timeline/
        Merged, chronological feed of structured Activity entries (calls,
        emails, WhatsApp touches, status changes) and legacy free-text
        InquiryNote entries for one lead.
        Permissions: IsSalesAgentOrAdmin.
    """

    permission_classes = [IsSalesAgentOrAdmin]

    def get(self, request, inquiry_number, *args, **kwargs):
        inquiry = _get_inquiry(inquiry_number)

        activities = Activity.objects.filter(inquiry=inquiry).select_related("author")
        notes = InquiryNote.objects.filter(inquiry=inquiry).select_related("author")

        entries = [
            {"entry_type": "activity", "created_at": a.created_at, "data": ActivitySerializer(a).data}
            for a in activities
        ] + [
            {"entry_type": "note", "created_at": n.created_at, "data": InquiryNoteSerializer(n).data}
            for n in notes
        ]
        entries.sort(key=lambda e: e["created_at"], reverse=True)

        return Response(entries, status=status.HTTP_200_OK)


class ActivityListCreateView(generics.ListCreateAPIView):
    """
    GET /api/v1/inquiries/{inquiry_number}/activities/
        List structured timeline entries (calls, emails, WhatsApp, status changes).
        Permissions: IsSalesAgentOrAdmin.

    POST /api/v1/inquiries/{inquiry_number}/activities/
        Log a call/email/WhatsApp touch or internal note. Stamps
        Inquiry.first_response_at on the first outreach-channel entry.
        Permissions: IsSalesAgentOrAdmin.
    """

    permission_classes = [IsSalesAgentOrAdmin]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ActivityCreateSerializer
        return ActivitySerializer

    def get_inquiry(self):
        return _get_inquiry(self.kwargs.get("inquiry_number"))

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Activity.objects.none()
        return Activity.objects.filter(inquiry=self.get_inquiry()).select_related("author")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["inquiry"] = self.get_inquiry()
        return context
