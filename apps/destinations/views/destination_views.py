from django.db.models import Count, Q
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import generics, status
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.common.permissions import IsAdminRole
from apps.destinations.models import Destination
from apps.destinations.serializers import (
    DestinationDetailSerializer,
    DestinationListSerializer,
    DestinationWriteSerializer,
)


class DestinationListCreateView(generics.ListCreateAPIView):
    """
    Public catalog list of travel destinations annotated with active trip counts.
    Admins can create new destinations.
    """

    search_fields = ["name", "region_name", "country"]
    ordering_fields = ["name", "country", "created_at"]
    filter_backends = [SearchFilter, OrderingFilter]

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAdminRole()]
        return [AllowAny()]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return DestinationWriteSerializer
        return DestinationListSerializer

    def get_queryset(self):
        # Admins can view all destinations including inactive ones
        if self.request.user.is_authenticated and getattr(self.request.user, "role", None) == "ADMIN":
            return Destination.objects.annotate(
                trips_count=Count("trips", filter=Q(trips__is_active=True))
            ).order_by("name")

        return Destination.objects.filter(is_active=True).annotate(
            trips_count=Count("trips", filter=Q(trips__is_active=True))
        ).order_by("name")

    @extend_schema(
        tags=["Destinations"],
        responses={200: DestinationListSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        response.success_message = "Destinations retrieved successfully."
        return response

    @extend_schema(
        tags=["Destinations Admin"],
        request=DestinationWriteSerializer,
        responses={
            201: DestinationDetailSerializer,
            400: OpenApiResponse(description="Validation error."),
            403: OpenApiResponse(description="Forbidden: Admin role required."),
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        destination = serializer.save()
        output_serializer = DestinationDetailSerializer(destination)
        response = Response(output_serializer.data, status=status.HTTP_201_CREATED)
        response.success_message = "Destination created successfully."
        return response


class DestinationDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Detailed destination landing page by slug.
    Admins can update or delete destinations.
    """

    lookup_field = "slug"

    def get_permissions(self):
        if self.request.method in ["PATCH", "PUT", "DELETE"]:
            return [IsAdminRole()]
        return [AllowAny()]

    def get_serializer_class(self):
        if self.request.method in ["PATCH", "PUT"]:
            return DestinationWriteSerializer
        return DestinationDetailSerializer

    def get_queryset(self):
        return Destination.objects.annotate(
            trips_count=Count("trips", filter=Q(trips__is_active=True))
        )

    @extend_schema(
        tags=["Destinations"],
        responses={
            200: DestinationDetailSerializer,
            404: OpenApiResponse(description="Destination not found."),
        },
    )
    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        response.success_message = "Destination details retrieved successfully."
        return response

    @extend_schema(
        tags=["Destinations Admin"],
        request=DestinationWriteSerializer,
        responses={
            200: DestinationDetailSerializer,
            400: OpenApiResponse(description="Validation error."),
            403: OpenApiResponse(description="Forbidden: Admin role required."),
            404: OpenApiResponse(description="Destination not found."),
        },
    )
    def patch(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        destination = serializer.save()
        output_serializer = DestinationDetailSerializer(destination)
        response = Response(output_serializer.data, status=status.HTTP_200_OK)
        response.success_message = "Destination updated successfully."
        return response

    @extend_schema(
        tags=["Destinations Admin"],
        responses={
            204: OpenApiResponse(description="Destination deleted successfully."),
            403: OpenApiResponse(description="Forbidden: Admin role required."),
            404: OpenApiResponse(description="Destination not found."),
        },
    )
    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        response = Response(status=status.HTTP_204_NO_CONTENT)
        response.success_message = "Destination deleted successfully."
        return response
