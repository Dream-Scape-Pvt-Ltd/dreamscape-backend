from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import generics, status
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.serializers.user_serializers import (
    UserAdminSerializer,
    UserProfileSerializer,
)
from apps.common.permissions import IsAdminRole

User = get_user_model()


class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    Retrieve or update the authenticated user's self profile.
    Email, role, and ID cannot be changed through this endpoint.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = UserProfileSerializer

    def get_object(self):
        return self.request.user

    @extend_schema(
        tags=["Users"],
        responses={
            200: UserProfileSerializer,
            401: OpenApiResponse(description="Authentication credentials were not provided."),
        },
    )
    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        response.success_message = "User profile retrieved successfully."
        return response

    @extend_schema(
        tags=["Users"],
        responses={
            200: UserProfileSerializer,
            400: OpenApiResponse(description="Validation error."),
            401: OpenApiResponse(description="Authentication credentials were not provided."),
        },
    )
    def patch(self, request, *args, **kwargs):
        response = super().patch(request, *args, **kwargs)
        response.success_message = "User profile updated successfully."
        return response

    @extend_schema(tags=["Users"])
    def put(self, request, *args, **kwargs):
        # Override to support full update if submitted
        response = super().put(request, *args, **kwargs)
        response.success_message = "User profile updated successfully."
        return response


class UserListView(generics.ListAPIView):
    """
    List all user accounts in the system.
    Restricted to ADMIN role. Supports pagination, searching and ordering.
    """

    permission_classes = [IsAdminRole]
    serializer_class = UserAdminSerializer
    queryset = User.objects.all().order_by("-date_joined")
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["email", "first_name", "last_name", "phone"]
    ordering_fields = ["date_joined", "email", "role", "last_login"]

    @extend_schema(
        tags=["Users Admin"],
        responses={
            200: UserAdminSerializer(many=True),
            401: OpenApiResponse(description="Unauthorized."),
            403: OpenApiResponse(description="Forbidden: Admin role required."),
        },
    )
    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        response.success_message = "User list retrieved successfully."
        return response


class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Admin-only endpoint to view, update, or soft-delete/deactivate a specific user account.
    """

    permission_classes = [IsAdminRole]
    serializer_class = UserAdminSerializer
    queryset = User.objects.all()
    lookup_field = "pk"

    @extend_schema(
        tags=["Users Admin"],
        responses={
            200: UserAdminSerializer,
            403: OpenApiResponse(description="Forbidden: Admin role required."),
            404: OpenApiResponse(description="User not found."),
        },
    )
    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        response.success_message = "User retrieved successfully."
        return response

    @extend_schema(
        tags=["Users Admin"],
        responses={
            200: UserAdminSerializer,
            400: OpenApiResponse(description="Validation error."),
            403: OpenApiResponse(description="Forbidden: Admin role required."),
            404: OpenApiResponse(description="User not found."),
        },
    )
    def patch(self, request, *args, **kwargs):
        response = super().patch(request, *args, **kwargs)
        response.success_message = "User updated successfully."
        return response

    @extend_schema(
        tags=["Users Admin"],
        responses={
            204: OpenApiResponse(description="User deleted successfully."),
            403: OpenApiResponse(description="Forbidden: Admin role required."),
            404: OpenApiResponse(description="User not found."),
        },
    )
    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        response = Response(status=status.HTTP_204_NO_CONTENT)
        response.success_message = "User deleted successfully."
        return response
