from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import generics, status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.common.permissions import IsAdminRole
from apps.trips.models import Trip, TripReview
from apps.trips.serializers import (
    TripReviewCreateSerializer,
    TripReviewModerationSerializer,
    TripReviewReadSerializer,
)


class ReviewListCreateView(generics.ListCreateAPIView):
    """
    List published reviews for a trip, or submit a new customer review.
    Submitted reviews enter the moderation queue.
    """

    permission_classes = [AllowAny]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return TripReviewCreateSerializer
        return TripReviewReadSerializer

    def get_trip(self):
        slug = self.kwargs.get("slug")
        trip = Trip.objects.filter(slug=slug).first()
        if not trip:
            raise NotFound(detail=f"Trip with slug '{slug}' not found.")
        return trip

    def get_queryset(self):
        trip = self.get_trip()
        # Admins can see all reviews (including unmoderated)
        if self.request.user.is_authenticated and getattr(self.request.user, "role", None) == "ADMIN":
            return TripReview.objects.filter(trip=trip).order_by("-created_at")
        return TripReview.objects.filter(trip=trip, is_published=True).order_by("-created_at")

    @extend_schema(
        tags=["Trips"],
        responses={200: TripReviewReadSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        response.success_message = "Reviews retrieved successfully."
        return response

    @extend_schema(
        tags=["Trips"],
        request=TripReviewCreateSerializer,
        responses={
            201: TripReviewReadSerializer,
            400: OpenApiResponse(description="Validation error."),
            404: OpenApiResponse(description="Trip not found."),
        },
    )
    def post(self, request, *args, **kwargs):
        trip = self.get_trip()
        data = request.data.copy()
        data["trip"] = str(trip.id)
        serializer = self.get_serializer(data=data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        review = serializer.save()
        output_serializer = TripReviewReadSerializer(review)
        response = Response(output_serializer.data, status=status.HTTP_201_CREATED)
        response.success_message = "Review submitted successfully. It will be visible after moderation."
        return response


class ReviewModerationView(generics.UpdateAPIView):
    """
    Admin moderation endpoint to approve, publish, or verify a review.
    """

    permission_classes = [IsAdminRole]
    serializer_class = TripReviewModerationSerializer
    lookup_url_kwarg = "review_id"

    def get_object(self):
        slug = self.kwargs.get("slug")
        review_id = self.kwargs.get("review_id")
        try:
            return TripReview.objects.get(trip__slug=slug, pk=review_id)
        except TripReview.DoesNotExist:
            raise NotFound(detail=f"Review '{review_id}' not found for trip '{slug}'.")

    @extend_schema(
        tags=["Trips Admin"],
        request=TripReviewModerationSerializer,
        responses={
            200: TripReviewReadSerializer,
            400: OpenApiResponse(description="Validation error."),
            403: OpenApiResponse(description="Forbidden: Admin role required."),
            404: OpenApiResponse(description="Review not found."),
        },
    )
    def patch(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        review = serializer.save()
        output_serializer = TripReviewReadSerializer(review)
        response = Response(output_serializer.data, status=status.HTTP_200_OK)
        response.success_message = "Review moderation status updated successfully."
        return response
