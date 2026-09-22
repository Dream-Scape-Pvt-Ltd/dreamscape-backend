from django.shortcuts import get_object_or_404
from rest_framework import generics

from apps.common.permissions import IsSalesAgentOrAdmin
from apps.inquiries.models import Inquiry, Task
from apps.inquiries.serializers import TaskCreateSerializer, TaskSerializer, TaskUpdateSerializer


class TaskListCreateView(generics.ListCreateAPIView):
    """
    GET /api/v1/inquiries/{inquiry_number}/tasks/
        List follow-up tasks scheduled against a lead.
        Permissions: IsSalesAgentOrAdmin.

    POST /api/v1/inquiries/{inquiry_number}/tasks/
        Schedule a follow-up task, defaulting to the requesting agent.
        Permissions: IsSalesAgentOrAdmin.
    """

    permission_classes = [IsSalesAgentOrAdmin]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return TaskCreateSerializer
        return TaskSerializer

    def get_inquiry(self):
        return get_object_or_404(Inquiry, inquiry_number=self.kwargs.get("inquiry_number"))

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Task.objects.none()
        return (
            Task.objects.filter(inquiry=self.get_inquiry())
            .select_related("assigned_agent", "inquiry")
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["inquiry"] = self.get_inquiry()
        return context


class MyTasksView(generics.ListAPIView):
    """
    GET /api/v1/tasks/mine/
        The requesting agent's open follow-up tasks, soonest due first.
        Powers the "My Tasks" panel on the admin dashboard.
        Filters: ?status= (defaults to OPEN)
        Permissions: IsSalesAgentOrAdmin.
    """

    permission_classes = [IsSalesAgentOrAdmin]
    serializer_class = TaskSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Task.objects.none()

        status_filter = self.request.query_params.get("status", "OPEN")
        qs = Task.objects.filter(assigned_agent=self.request.user).select_related("inquiry", "assigned_agent")
        if status_filter:
            qs = qs.filter(status=status_filter.upper())
        return qs.order_by("due_at")


class TaskDetailUpdateView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET/PATCH/DELETE /api/v1/tasks/{id}/
        Retrieve, mark done/cancelled, or delete a follow-up task.
        Permissions: IsSalesAgentOrAdmin.
    """

    permission_classes = [IsSalesAgentOrAdmin]
    queryset = Task.objects.select_related("inquiry", "assigned_agent")

    def get_serializer_class(self):
        if self.request.method in ("PATCH", "PUT"):
            return TaskUpdateSerializer
        return TaskSerializer
