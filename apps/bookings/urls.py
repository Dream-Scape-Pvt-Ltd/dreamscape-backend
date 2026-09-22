from django.urls import path
from apps.bookings.views import (
    BookingListCreateView,
    BookingDetailView,
    BookingCancelView,
    PassengerListView,
    PassengerDetailView,
    WaitlistJoinView,
    DepartureWaitlistView,
    WaitlistPromoteView,
)

app_name = "bookings"

urlpatterns = [
    path("", BookingListCreateView.as_view(), name="booking-list-create"),

    # Waitlist routes must precede <str:booking_reference>/, which would
    # otherwise match "waitlist" as a booking reference.
    path("waitlist/", WaitlistJoinView.as_view(), name="waitlist-join"),
    path(
        "waitlist/departures/<uuid:departure_id>/",
        DepartureWaitlistView.as_view(),
        name="waitlist-departure",
    ),
    path(
        "waitlist/departures/<uuid:departure_id>/promote/",
        WaitlistPromoteView.as_view(),
        name="waitlist-promote",
    ),

    path("<str:booking_reference>/", BookingDetailView.as_view(), name="booking-detail"),
    path("<str:booking_reference>/cancel/", BookingCancelView.as_view(), name="booking-cancel"),
    path("<str:booking_reference>/passengers/", PassengerListView.as_view(), name="passenger-list"),
    path("<str:booking_reference>/passengers/<uuid:passenger_id>/", PassengerDetailView.as_view(), name="passenger-detail"),
]
