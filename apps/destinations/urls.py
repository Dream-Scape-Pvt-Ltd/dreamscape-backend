from django.urls import path

from apps.destinations.views import (
    ActivityCategoryDetailView,
    ActivityCategoryListCreateView,
    DestinationDetailView,
    DestinationListCreateView,
    NavigationMenuDetailView,
    NavigationMenuListCreateView,
)

app_name = "destinations"

urlpatterns = [
    path("", DestinationListCreateView.as_view(), name="destination-list"),
    path("activity-categories/", ActivityCategoryListCreateView.as_view(), name="category-list"),
    path("activity-categories/<slug:slug>/", ActivityCategoryDetailView.as_view(), name="category-detail"),
    path("nav-menus/", NavigationMenuListCreateView.as_view(), name="nav-menu-list"),
    path("nav-menus/<slug:slug>/", NavigationMenuDetailView.as_view(), name="nav-menu-detail"),
    path("<slug:slug>/", DestinationDetailView.as_view(), name="destination-detail"),
]
