"""
apps.content_cms URL configuration -- Phase 0 stub.
Endpoints will be registered in their respective implementation phase.
"""
from django.urls import path
from apps.content_cms.views import GuideCommentDetailView, GuideCommentListCreateView, GuideImageUploadView, GuideViewCountView, TravelGuideListCreateView, TravelGuideDetailView, ResponsibleTravelListCreateView, ResponsibleTravelDetailView, TrekGuideListCreateView, TrekGuideDetailView

app_name = 'content_cms'

urlpatterns = [
    path('guides/', TravelGuideListCreateView.as_view(), name='guide-list'),
    path('guides/media/upload/', GuideImageUploadView.as_view(), name='guide-image-upload'),
    path('guides/<slug:slug>/view/', GuideViewCountView.as_view(), name='guide-view-count'),
    path('guides/<slug:slug>/comments/', GuideCommentListCreateView.as_view(), name='guide-comments'),
    path('guides/<slug:slug>/comments/<uuid:comment_id>/', GuideCommentDetailView.as_view(), name='guide-comment-detail'),
    path('guides/<slug:slug>/', TravelGuideDetailView.as_view(), name='guide-detail'),
    path('responsible-travel/', ResponsibleTravelListCreateView.as_view(), name='initiative-list'),
    path('responsible-travel/<slug:slug>/', ResponsibleTravelDetailView.as_view(), name='initiative-detail'),
    path('trek-guides/', TrekGuideListCreateView.as_view(), name='trek-guide-list'),
    path('trek-guides/<slug:slug>/', TrekGuideDetailView.as_view(), name='trek-guide-detail'),
]
