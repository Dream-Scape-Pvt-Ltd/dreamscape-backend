from django.utils import timezone
from rest_framework import serializers

from apps.accounts.serializers.user_serializers import UserMinimalSerializer
from apps.inquiries.models import Activity, ActivityChannel, OUTREACH_CHANNELS


class ActivitySerializer(serializers.ModelSerializer):
    """
    Structured CRM timeline entry: a logged call, email, WhatsApp touch,
    status transition, or system event.
    """

    author = UserMinimalSerializer(read_only=True)

    class Meta:
        model = Activity
        fields = ["id", "author", "channel", "body", "metadata", "created_at"]
        read_only_fields = ["id", "author", "metadata", "created_at"]


class ActivityCreateSerializer(serializers.ModelSerializer):
    """
    Agent-facing write serializer for logging a call/email/WhatsApp touch
    or internal note against an inquiry. Stamps Inquiry.first_response_at
    the first time an outreach-channel activity is logged.
    """

    class Meta:
        model = Activity
        fields = ["id", "channel", "body", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_channel(self, value):
        if value == ActivityChannel.STATUS_CHANGE:
            raise serializers.ValidationError(
                "STATUS_CHANGE activities are created automatically and cannot be logged manually."
            )
        return value

    def create(self, validated_data):
        inquiry = self.context["inquiry"]
        request = self.context.get("request")
        author = request.user if request and request.user.is_authenticated else None

        activity = Activity.objects.create(inquiry=inquiry, author=author, **validated_data)

        if activity.channel in OUTREACH_CHANNELS and not inquiry.first_response_at:
            inquiry.first_response_at = timezone.now()
            inquiry.save(update_fields=["first_response_at", "updated_at"])

        return activity
