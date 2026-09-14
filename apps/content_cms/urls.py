"""
apps.content_cms URL configuration -- Phase 0 stub.
Endpoints will be registered in their respective implementation phase.
"""
from django.urls import path
from apps.content_cms.views import TravelGuideListCreateView, TravelGuideDetailView, ResponsibleTravelListCreateView, ResponsibleTravelDetailView

app_name = 'content_cms'

urlpatterns = [
    path('guides/', TravelGuideListCreateView.as_view(), name='guide-list'),
    path('guides/<slug:slug>/', TravelGuideDetailView.as_view(), name='guide-detail'),
    path('responsible-travel/', ResponsibleTravelListCreateView.as_view(), name='initiative-list'),
    path('responsible-travel/<slug:slug>/', ResponsibleTravelDetailView.as_view(), name='initiative-detail'),
]
