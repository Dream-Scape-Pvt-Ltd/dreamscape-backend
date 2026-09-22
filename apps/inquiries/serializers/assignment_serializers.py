from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from apps.accounts.serializers.user_serializers import UserMinimalSerializer
from apps.inquiries.models import (
    Activity,
    ActivityChannel,
    Inquiry,
    InquiryStatus,
    LeadAssignmentRule,
)
from apps.inquiries.serializers.inquiry_serializers import assignable_agents
from apps.trips.models import TripDeparture


class LeadAssignmentRuleSerializer(serializers.ModelSerializer):
    """Read serializer for a tour-based routing rule."""

    agent = UserMinimalSerializer(read_only=True)
    target_label = serializers.CharField(read_only=True)
    trip_title = serializers.CharField(source="trip.title", read_only=True, default=None)
    destination_name = serializers.CharField(
        source="destination.name", read_only=True, default=None
    )

    class Meta:
        model = LeadAssignmentRule
        fields = [
            "id",
            "departure",
            "trip",
            "trip_title",
            "destination",
            "destination_name",
            "agent",
            "target_label",
            "priority",
            "is_active",
            "created_at",
        ]
        read_only_fields = fields


class LeadAssignmentRuleWriteSerializer(serializers.ModelSerializer):
    """Admin write serializer for routing rules."""

    agent_id = serializers.PrimaryKeyRelatedField(
        queryset=assignable_agents(),
        source="agent",
    )

    class Meta:
        model = LeadAssignmentRule
        fields = [
            "id",
            "departure",
            "trip",
            "destination",
            "agent_id",
            "priority",
            "is_active",
        ]

    def validate(self, attrs):
        def resolved(name):
            return attrs[name] if name in attrs else getattr(self.instance, name, None)

        departure = resolved("departure")
        trip = resolved("trip")
        destination = resolved("destination")

        if not any([departure, trip, destination]):
            raise serializers.ValidationError(
                "A rule must target a departure, a trip, or a destination."
            )
        # Mirrors resolve_agent, which looks at only the most specific target.
        # Setting two would silently ignore the broader one.
        if departure and (trip or destination):
            raise serializers.ValidationError(
                "A departure rule already implies its trip; leave trip and destination empty."
            )
        if trip and destination:
            raise serializers.ValidationError(
                "A trip rule already implies its destination; leave destination empty."
            )
        return attrs


class BulkAssignSerializer(serializers.Serializer):
    """
    Reassign many leads to one agent in a single atomic operation.

    Accepts either an explicit list of inquiry numbers, or a tour selector
    (trip and/or departure) — the "give every Annapurna departure to this
    specialist" case.
    """

    agent_id = serializers.PrimaryKeyRelatedField(
        queryset=assignable_agents(),
        source="agent",
    )
    inquiry_numbers = serializers.ListField(
        child=serializers.CharField(max_length=30),
        required=False,
        allow_empty=False,
    )
    trip = serializers.SlugField(required=False, allow_blank=True)
    departure = serializers.UUIDField(required=False, allow_null=True)
    only_unassigned = serializers.BooleanField(default=False)
    include_closed = serializers.BooleanField(
        default=False,
        help_text="By default only open leads (NEW/ASSIGNED/IN_CONTACT) are reassigned.",
    )

    def validate(self, attrs):
        if not attrs.get("inquiry_numbers") and not attrs.get("trip") and not attrs.get("departure"):
            raise serializers.ValidationError(
                "Provide inquiry_numbers, or a trip/departure to select a batch."
            )
        if attrs.get("departure"):
            if not TripDeparture.objects.filter(id=attrs["departure"]).exists():
                raise serializers.ValidationError(
                    {"departure": "Selected departure does not exist."}
                )
        return attrs

    def _queryset(self):
        data = self.validated_data
        # No select_related here: select_for_update() cannot lock across the
        # nullable outer join that assigned_agent would add. The rows carry
        # assigned_agent_id, which is all the audit trail needs.
        qs = Inquiry.objects.all()

        if data.get("inquiry_numbers"):
            qs = qs.filter(inquiry_number__in=data["inquiry_numbers"])
        if data.get("trip"):
            qs = qs.filter(trip__slug__iexact=data["trip"])
        if data.get("departure"):
            qs = qs.filter(departure_id=data["departure"])
        if data.get("only_unassigned"):
            qs = qs.filter(assigned_agent__isnull=True)
        if not data.get("include_closed"):
            qs = qs.filter(
                status__in=[
                    InquiryStatus.NEW,
                    InquiryStatus.ASSIGNED,
                    InquiryStatus.IN_CONTACT,
                ]
            )
        return qs

    def assign(self):
        agent = self.validated_data["agent"]
        request = self.context.get("request")
        author = request.user if request and request.user.is_authenticated else None

        now = timezone.now()

        with transaction.atomic():
            inquiries = list(self._queryset().select_for_update())
            reassigned = []
            activities = []

            for inquiry in inquiries:
                old_agent_id = inquiry.assigned_agent_id
                if old_agent_id == agent.id:
                    continue  # already owned by this agent; nothing to record

                inquiry.assigned_agent = agent
                if inquiry.status == InquiryStatus.NEW:
                    inquiry.status = InquiryStatus.ASSIGNED
                # bulk_update bypasses save(), so auto_now never fires here.
                inquiry.updated_at = now
                reassigned.append(inquiry)
                activities.append(
                    Activity(
                        inquiry=inquiry,
                        author=author,
                        channel=ActivityChannel.SYSTEM,
                        body=f"Bulk reassigned to {agent.get_full_name() or agent.email}.",
                        metadata={
                            "from_agent": str(old_agent_id) if old_agent_id else None,
                            "to_agent": str(agent.id),
                            "reason": "bulk_assign",
                        },
                    )
                )

            if reassigned:
                Inquiry.objects.bulk_update(
                    reassigned, ["assigned_agent", "status", "updated_at"]
                )
                Activity.objects.bulk_create(activities)

        return {
            "matched": len(inquiries),
            "reassigned": len(reassigned),
            "agent": UserMinimalSerializer(agent).data,
        }
