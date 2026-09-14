from django.urls import path

from apps.trips.views import (
    DepartureDetailView,
    DepartureListCreateView,
    ExpeditionDetailView,
    ItineraryDayDetailView,
    ItineraryView,
    ReviewListCreateView,
    ReviewModerationView,
    TripDetailView,
    TripListCreateView,
)

app_name = "trips"

urlpatterns = [
    path("", TripListCreateView.as_view(), name="trip-list"),
    path("<slug:slug>/itinerary/", ItineraryView.as_view(), name="trip-itinerary"),
    path("<slug:slug>/itinerary/<int:day_number>/", ItineraryDayDetailView.as_view(), name="itinerary-day"),
    path("<slug:slug>/departures/", DepartureListCreateView.as_view(), name="departure-list"),
    path("<slug:slug>/departures/<uuid:departure_id>/", DepartureDetailView.as_view(), name="departure-detail"),
    path("<slug:slug>/reviews/", ReviewListCreateView.as_view(), name="review-list"),
    path("<slug:slug>/reviews/<uuid:review_id>/", ReviewModerationView.as_view(), name="review-moderation"),
    path("<slug:slug>/expedition-detail/", ExpeditionDetailView.as_view(), name="expedition-detail"),
    # Must remain last to avoid matching sub-resources above
    path("<slug:slug>/", TripDetailView.as_view(), name="trip-detail"),
]
