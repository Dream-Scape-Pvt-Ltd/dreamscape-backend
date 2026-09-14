from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.common.permissions import IsAdminRole
from apps.destinations.models import ActivityCategory
from apps.destinations.serializers import ActivityCategorySerializer


class ActivityCategoryListCreateView(generics.ListCreateAPIView):
    """
    List all active activity categories (Trekking, Mountaineering, Cultural, etc.)
    Admins can create new categories.
    """

    serializer_class = ActivityCategorySerializer

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAdminRole()]
        return [AllowAny()]

    def get_queryset(self):
        if self.request.user.is_authenticated and getattr(self.request.user, "role", None) == "ADMIN":
            return ActivityCategory.objects.all().order_by("name")
        return ActivityCategory.objects.filter(is_active=True).order_by("name")

    @extend_schema(
        tags=["Categories"],
        responses={200: ActivityCategorySerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        response.success_message = "Activity categories retrieved successfully."
        return response

    @extend_schema(
        tags=["Categories Admin"],
        request=ActivityCategorySerializer,
        responses={
            201: ActivityCategorySerializer,
            400: OpenApiResponse(description="Validation error."),
            403: OpenApiResponse(description="Forbidden: Admin role required."),
        },
    )
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        response.success_message = "Activity category created successfully."
        return response


class ActivityCategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve activity category details by slug.
    Admins can update or delete categories.
    """

    lookup_field = "slug"
    serializer_class = ActivityCategorySerializer

    def get_permissions(self):
        if self.request.method in ["PATCH", "PUT", "DELETE"]:
            return [IsAdminRole()]
        return [AllowAny()]

    def get_queryset(self):
        return ActivityCategory.objects.all()

    @extend_schema(
        tags=["Categories"],
        responses={
            200: ActivityCategorySerializer,
            404: OpenApiResponse(description="Category not found."),
        },
    )
    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        response.success_message = "Activity category retrieved successfully."
        return response

    @extend_schema(
        tags=["Categories Admin"],
        request=ActivityCategorySerializer,
        responses={
            200: ActivityCategorySerializer,
            400: OpenApiResponse(description="Validation error."),
            403: OpenApiResponse(description="Forbidden: Admin role required."),
        },
    )
    def patch(self, request, *args, **kwargs):
        response = super().patch(request, *args, **kwargs)
        response.success_message = "Activity category updated successfully."
        return response

    @extend_schema(
        tags=["Categories Admin"],
        responses={
            204: OpenApiResponse(description="Category deleted successfully."),
            403: OpenApiResponse(description="Forbidden: Admin role required."),
        },
    )
    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        response = Response(status=status.HTTP_204_NO_CONTENT)
        response.success_message = "Activity category deleted successfully."
        return response
