from django.urls import path

from apps.destinations.views import (
    ActivityCategoryDetailView,
    ActivityCategoryListCreateView,
    DestinationDetailView,
    DestinationListCreateView,
)

app_name = "destinations"

urlpatterns = [
    path("", DestinationListCreateView.as_view(), name="destination-list"),
    path("activity-categories/", ActivityCategoryListCreateView.as_view(), name="category-list"),
    path("activity-categories/<slug:slug>/", ActivityCategoryDetailView.as_view(), name="category-detail"),
    path("<slug:slug>/", DestinationDetailView.as_view(), name="destination-detail"),
]
