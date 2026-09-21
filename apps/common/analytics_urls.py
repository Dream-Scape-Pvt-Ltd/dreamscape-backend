from django.urls import path
from apps.common.analytics_views import DashboardAnalyticsView

urlpatterns = [
    path("dashboard/", DashboardAnalyticsView.as_view(), name="dashboard-analytics"),
]
