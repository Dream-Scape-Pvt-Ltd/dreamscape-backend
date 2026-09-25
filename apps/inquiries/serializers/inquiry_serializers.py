from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers

from apps.accounts.serializers.user_serializers import UserMinimalSerializer
from apps.inquiries.models import (
    Customer,
    Inquiry,
    InquiryNote,
    InquiryType,
    InquiryStatus,
    LostReason,
    TailorMadeRequest,
)
from apps.inquiries.serializers.activity_serializers import ActivitySerializer
from apps.inquiries.serializers.tag_serializers import TagSerializer
from apps.inquiries.serializers.tailor_made_serializers import TailorMadeRequestSerializer
from apps.inquiries.tasks import send_inquiry_acknowledgement_email, send_agent_whatsapp_alert
from apps.inquiries.utils import generate_inquiry_number
from apps.trips.models import Trip, TripDeparture
from apps.trips.serializers.departure_serializers import TripDepartureSerializer

User = get_user_model()


def assignable_agents():
    """
    Staff who may own a CRM lead.

    A lazily-evaluated queryset, so it is safe to bind at class-definition time
    in a serializer field.
    """
    from apps.accounts.models import UserRole

    return User.objects.filter(
        role__in=[UserRole.ADMIN, UserRole.SALES_AGENT],
        is_active=True,
    )


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

            customer = Customer.get_or_create_from_contact(
                email=validated_data["email"],
                full_name=validated_data.get("full_name", ""),
                phone=validated_data.get("phone", ""),
                whatsapp_number=validated_data.get("whatsapp_number", ""),
            )
            customer.lifetime_inquiries = customer.inquiries.count() + 1
            customer.save(update_fields=["lifetime_inquiries", "updated_at"])

            inquiry = Inquiry.objects.create(
                inquiry_number=inq_num,
                status=InquiryStatus.NEW,
                customer=customer,
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
    assigned_agent_id = serializers.UUIDField(source="assigned_agent.id", read_only=True, default=None)
    trip_title = serializers.CharField(source="trip.title", read_only=True)
    trip_slug = serializers.CharField(source="trip.slug", read_only=True)
    departure_label = serializers.SerializerMethodField()
    tags = TagSerializer(many=True, read_only=True)

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
            "trip_slug",
            "departure",
            "departure_label",
            "assigned_agent_name",
            "assigned_agent_id",
            "tags",
            "sla_breached",
            "group_size",
            "travelers_count",
            "revenue_usd",
            "created_at",
        ]

    def get_assigned_agent_name(self, obj) -> str | None:
        if obj.assigned_agent:
            return obj.assigned_agent.get_full_name() or obj.assigned_agent.email
        return None

    def get_departure_label(self, obj) -> str | None:
        """Human-readable batch identity for the CRM's tour column."""
        if not obj.departure_id:
            return None
        return f"{obj.departure.start_date:%d %b %Y} – {obj.departure.end_date:%d %b %Y}"


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
    activities = ActivitySerializer(many=True, read_only=True)
    tailor_made_detail = TailorMadeRequestSerializer(read_only=True)
    departure = TripDepartureSerializer(read_only=True)
    trip_title = serializers.CharField(source="trip.title", read_only=True)
    trip_slug = serializers.CharField(source="trip.slug", read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    converted_booking_reference = serializers.CharField(source="converted_booking.booking_reference", read_only=True, default=None)

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
            "lost_reason",
            "assigned_agent",
            "tailor_made_detail",
            "notes",
            "activities",
            "tags",
            "first_response_at",
            "sla_breached",
            "travelers_count",
            "seats_held",
            "revenue_usd",
            "converted_booking_reference",
            "converted_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class InquiryUpdateSerializer(serializers.ModelSerializer):
    """
    Agent write serializer for CRM pipeline state transitions and agent assignment.

    Moving a lead into BOOKED puts its travellers on a departure (the lead's
    own, or ``departure_id``), taking ``travelers_count`` seats — the group size
    by default. Status changes go through ``transition_status`` so the seat
    ledger and trip revenue stay in step.
    """

    # Scoped to staff who can actually work a lead. An unscoped queryset let
    # any user id through, including customers and B2B partners.
    assigned_agent_id = serializers.PrimaryKeyRelatedField(
        queryset=assignable_agents(),
        source="assigned_agent",
        required=False,
        allow_null=True,
    )
    departure_id = serializers.PrimaryKeyRelatedField(
        queryset=TripDeparture.objects.all(),
        required=False,
        write_only=True,
    )
    travelers_count = serializers.IntegerField(required=False, min_value=1, write_only=True)

    class Meta:
        model = Inquiry
        fields = [
            "status",
            "assigned_agent_id",
            "lost_reason",
            "departure_id",
            "travelers_count",
        ]

    def validate(self, attrs):
        new_status = attrs.get("status", self.instance.status if self.instance else None)
        if new_status == InquiryStatus.CLOSED:
            lost_reason = attrs.get("lost_reason") or (self.instance.lost_reason if self.instance else "")
            already_converted = self.instance and self.instance.converted_booking_id
            if not lost_reason and not already_converted:
                raise serializers.ValidationError({
                    "lost_reason": "A lost reason is required when closing an inquiry that did not convert to a booking."
                })
        return attrs

    def update(self, instance, validated_data):
        from apps.inquiries.models import Activity, ActivityChannel
        from apps.inquiries.services import transition_status

        request = self.context.get("request")
        author = request.user if request and request.user.is_authenticated else None

        new_status = validated_data.pop("status", instance.status)
        departure = validated_data.pop("departure_id", None)
        travelers = validated_data.pop("travelers_count", None)
        old_agent = instance.assigned_agent

        with transaction.atomic():
            updated = super().update(instance, validated_data)
            updated = transition_status(
                updated,
                new_status,
                author=author,
                departure=departure,
                travelers=travelers,
            )

            new_agent = validated_data.get("assigned_agent", old_agent)
            if "assigned_agent" in validated_data and new_agent != old_agent:
                Activity.objects.create(
                    inquiry=updated,
                    author=author,
                    channel=ActivityChannel.SYSTEM,
                    body=f"Reassigned to {new_agent.get_full_name() if new_agent else 'unassigned'}.",
                    metadata={
                        "from_agent": str(old_agent.id) if old_agent else None,
                        "to_agent": str(new_agent.id) if new_agent else None,
                    },
                )

        return updated
