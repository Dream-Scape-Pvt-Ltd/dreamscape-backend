import secrets
from rest_framework import serializers

from apps.accounts.serializers.user_serializers import UserMinimalSerializer
from apps.inquiries.models import Inquiry, InquiryNote, InquiryType, InquiryStatus, TailorMadeRequest
from apps.inquiries.serializers.tailor_made_serializers import TailorMadeRequestCreateSerializer


def generate_inquiry_number() -> str:
    """Generate reference in format INQ-2026-9082"""
    digits = secrets.randbelow(9000) + 1000
    return f"INQ-2026-{digits}"


class InquiryNoteSerializer(serializers.ModelSerializer):
    author = UserMinimalSerializer(read_only=True)

    class Meta:
        model = InquiryNote
        fields = ["id", "author", "note_text", "created_at"]
        read_only_fields = ["id", "author", "created_at"]


class InquiryCreateSerializer(serializers.ModelSerializer):
    """
    Public lead form serializer.
    Auto-generates inquiry_number and creates optional tailor-made details atomically.
    """

    tailor_made_detail = TailorMadeRequestCreateSerializer(required=False)

    class Meta:
        model = Inquiry
        fields = [
            "id",
            "inquiry_number",
            "inquiry_type",
            "trip",
            "departure",
            "full_name",
            "email",
            "phone",
            "whatsapp_number",
            "message",
            "preferred_dates",
            "estimated_budget",
            "group_size",
            "lead_source",
            "tailor_made_detail",
        ]
        read_only_fields = ["id", "inquiry_number"]

    def create(self, validated_data):
        tailor_made_data = validated_data.pop("tailor_made_detail", None)

        inq_num = generate_inquiry_number()
        while Inquiry.objects.filter(inquiry_number=inq_num).exists():
            inq_num = generate_inquiry_number()

        inquiry = Inquiry.objects.create(
            inquiry_number=inq_num,
            status=InquiryStatus.NEW,
            **validated_data,
        )

        if tailor_made_data or validated_data.get("inquiry_type") == InquiryType.TAILOR_MADE:
            tm_data = tailor_made_data or {}
            TailorMadeRequest.objects.create(inquiry=inquiry, **tm_data)

        return inquiry


class InquiryDetailSerializer(serializers.ModelSerializer):
    """
    CRM Lead dashboard view serializer.
    ORM Dependencies:
        select_related: 'trip', 'departure', 'assigned_agent'
        prefetch_related: 'tailor_made_detail', 'notes__author'
    """

    assigned_agent = UserMinimalSerializer(read_only=True)
    notes = InquiryNoteSerializer(many=True, read_only=True)
    tailor_made_detail = TailorMadeRequestCreateSerializer(read_only=True)
    trip_title = serializers.CharField(source="trip.title", read_only=True)

    class Meta:
        model = Inquiry
        fields = [
            "id",
            "inquiry_number",
            "inquiry_type",
            "trip",
            "trip_title",
            "departure",
            "full_name",
            "email",
            "phone",
            "whatsapp_number",
            "message",
            "preferred_dates",
            "estimated_budget",
            "group_size",
            "lead_source",
            "status",
            "assigned_agent",
            "tailor_made_detail",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
