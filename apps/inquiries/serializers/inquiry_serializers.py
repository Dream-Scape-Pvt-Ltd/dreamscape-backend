from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers

from apps.accounts.serializers.user_serializers import UserMinimalSerializer
from apps.inquiries.models import Inquiry, InquiryNote, InquiryType, InquiryStatus, TailorMadeRequest
from apps.inquiries.serializers.tailor_made_serializers import TailorMadeRequestSerializer
from apps.inquiries.tasks import send_inquiry_acknowledgement_email, send_agent_whatsapp_alert
from apps.inquiries.utils import generate_inquiry_number
from apps.trips.models import Trip, TripDeparture
from apps.trips.serializers.departure_serializers import TripDepartureSerializer

User = get_user_model()


class InquiryNoteSerializer(serializers.ModelSerializer):
    """
    Internal consultation note thread for sales agents and managers.
    Author is auto-assigned from request.user.
    """

    author = UserMinimalSerializer(read_only=True)

    class Meta:
        model = InquiryNote
        fields = ["id", "author", "note_text", "created_at"]
        read_only_fields = ["id", "author", "created_at"]


class InquiryCreateSerializer(serializers.ModelSerializer):
    """
    Public lead capture form serializer.
    Auto-generates inquiry_number.
    Atomically creates nested TailorMadeRequest for custom journeys.
    Dispatches asynchronous acknowledgement email and agent alerts.
    """

    tailor_made = TailorMadeRequestSerializer(required=False, allow_null=True)
    trip = serializers.PrimaryKeyRelatedField(
        queryset=Trip.objects.all(),
        required=False,
        allow_null=True,
    )
    departure = serializers.PrimaryKeyRelatedField(
        queryset=TripDeparture.objects.all(),
        required=False,
        allow_null=True,
    )

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
            "tailor_made",
        ]
        read_only_fields = ["id", "inquiry_number"]

    def to_internal_value(self, data):
        # Support both 'tailor_made' and 'tailor_made_detail' key names
        if "tailor_made_detail" in data and "tailor_made" not in data:
            data = data.copy() if hasattr(data, "copy") else dict(data)
            data["tailor_made"] = data.get("tailor_made_detail")
        return super().to_internal_value(data)

    def create(self, validated_data):
        tailor_made_data = validated_data.pop("tailor_made", None)

        with transaction.atomic():
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

        # Trigger async tasks
        try:
            send_inquiry_acknowledgement_email(inquiry.id)
            send_agent_whatsapp_alert(inquiry.id)
        except Exception:
            pass

        return inquiry


class InquiryListSerializer(serializers.ModelSerializer):
    """
    Compact CRM pipeline list serializer for sales agents and managers.
    """

    assigned_agent_name = serializers.SerializerMethodField()
    trip_title = serializers.CharField(source="trip.title", read_only=True)

    class Meta:
        model = Inquiry
        fields = [
            "id",
            "inquiry_number",
            "inquiry_type",
            "full_name",
            "email",
            "phone",
            "whatsapp_number",
            "status",
            "trip_title",
            "assigned_agent_name",
            "created_at",
        ]

    def get_assigned_agent_name(self, obj) -> str | None:
        if obj.assigned_agent:
            return obj.assigned_agent.get_full_name() or obj.assigned_agent.email
        return None


class InquiryDetailSerializer(serializers.ModelSerializer):
    """
    Full CRM Lead detail serializer with complete history, trip specs,
    tailor-made adventure preferences, and consultation note threads.
    ORM Dependencies:
        select_related: 'trip', 'departure', 'assigned_agent'
        prefetch_related: 'tailor_made_detail', 'notes__author'
    """

    assigned_agent = UserMinimalSerializer(read_only=True)
    notes = InquiryNoteSerializer(many=True, read_only=True)
    tailor_made_detail = TailorMadeRequestSerializer(read_only=True)
    departure = TripDepartureSerializer(read_only=True)
    trip_title = serializers.CharField(source="trip.title", read_only=True)
    trip_slug = serializers.CharField(source="trip.slug", read_only=True)

    class Meta:
        model = Inquiry
        fields = [
            "id",
            "inquiry_number",
            "inquiry_type",
            "trip",
            "trip_title",
            "trip_slug",
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


class InquiryUpdateSerializer(serializers.ModelSerializer):
    """
    Agent write serializer for CRM pipeline state transitions and agent assignment.
    """

    assigned_agent_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source="assigned_agent",
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Inquiry
        fields = [
            "status",
            "assigned_agent_id",
        ]
