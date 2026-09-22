from django.urls import path

from apps.accounts.views import (
    AgentListView,
    UserDetailView,
    UserListView,
    UserProfileView,
)

app_name = "users"

urlpatterns = [
    path("me/", UserProfileView.as_view(), name="user-profile"),
    path("agents/", AgentListView.as_view(), name="agent-list"),
    path("", UserListView.as_view(), name="user-list"),
    path("<uuid:pk>/", UserDetailView.as_view(), name="user-detail"),
]
