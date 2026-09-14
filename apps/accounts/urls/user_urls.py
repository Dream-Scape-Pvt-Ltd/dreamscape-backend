from django.urls import path

from apps.accounts.views import (
    UserDetailView,
    UserListView,
    UserProfileView,
)

app_name = "users"

urlpatterns = [
    path("me/", UserProfileView.as_view(), name="user-profile"),
    path("", UserListView.as_view(), name="user-list"),
    path("<uuid:pk>/", UserDetailView.as_view(), name="user-detail"),
]
