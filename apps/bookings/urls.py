from django.urls import path
from apps.bookings.views import (
    BookingListCreateView,
    BookingDetailView,
    BookingCancelView,
    PassengerListView,
    PassengerDetailView,
)

app_name = "bookings"

urlpatterns = [
    path("", BookingListCreateView.as_view(), name="booking-list-create"),
    path("<str:booking_reference>/", BookingDetailView.as_view(), name="booking-detail"),
    path("<str:booking_reference>/cancel/", BookingCancelView.as_view(), name="booking-cancel"),
    path("<str:booking_reference>/passengers/", PassengerListView.as_view(), name="passenger-list"),
    path("<str:booking_reference>/passengers/<uuid:passenger_id>/", PassengerDetailView.as_view(), name="passenger-detail"),
]
