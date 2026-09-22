from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers

from apps.accounts.serializers.user_serializers import UserMinimalSerializer
from apps.inquiries.models import Task, TaskStatus

User = get_user_model()


class TaskSerializer(serializers.ModelSerializer):
    """
    Follow-up reminder attached to a lead, surfaced in the agent's
    "My Tasks" panel.
    """

    assigned_agent = UserMinimalSerializer(read_only=True)
    inquiry_number = serializers.CharField(source="inquiry.inquiry_number", read_only=True)
    inquiry_full_name = serializers.CharField(source="inquiry.full_name", read_only=True)

    class Meta:
        model = Task
        fields = [
            "id",
            "inquiry",
            "inquiry_number",
            "inquiry_full_name",
            "assigned_agent",
            "title",
            "due_at",
            "status",
            "completed_at",
            "created_at",
        ]
        read_only_fields = ["id", "assigned_agent", "completed_at", "created_at"]


class TaskCreateSerializer(serializers.ModelSerializer):
    """
    Write serializer for scheduling a follow-up task on an inquiry.
    Defaults assigned_agent to the requesting user unless another agent
    is explicitly assigned.
    """

    assigned_agent_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source="assigned_agent",
        required=False,
    )

    class Meta:
        model = Task
        fields = ["id", "title", "due_at", "assigned_agent_id"]
        read_only_fields = ["id"]

    def create(self, validated_data):
        inquiry = self.context["inquiry"]
        request = self.context.get("request")
        if "assigned_agent" not in validated_data and request:
            validated_data["assigned_agent"] = request.user
        return Task.objects.create(inquiry=inquiry, **validated_data)


class TaskUpdateSerializer(serializers.ModelSerializer):
    """
    Agent write serializer for marking a follow-up task done or cancelled.
    """

    class Meta:
        model = Task
        fields = ["title", "due_at", "status"]

    def update(self, instance, validated_data):
        new_status = validated_data.get("status", instance.status)
        if new_status != instance.status and new_status == TaskStatus.DONE:
            validated_data["completed_at"] = timezone.now()
        elif new_status != instance.status and new_status != TaskStatus.DONE:
            validated_data["completed_at"] = None
        return super().update(instance, validated_data)
