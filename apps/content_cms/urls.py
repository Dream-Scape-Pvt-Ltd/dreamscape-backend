"""
apps.content_cms URL configuration -- Phase 0 stub.
Endpoints will be registered in their respective implementation phase.
"""
from django.urls import path
from apps.content_cms.views.site_settings_views import SiteSettingsView
from apps.content_cms.views import GuideCommentDetailView, GuideCommentListCreateView, GuideImageUploadView, GuideViewCountView, TravelGuideListCreateView, TravelGuideDetailView, ResponsibleTravelListCreateView, ResponsibleTravelDetailView

app_name = 'content_cms'

urlpatterns = [
    path('site-settings/', SiteSettingsView.as_view(), name='site-settings'),
    path('guides/', TravelGuideListCreateView.as_view(), name='guide-list'),
    path('guides/media/upload/', GuideImageUploadView.as_view(), name='guide-image-upload'),
    path('guides/<slug:slug>/view/', GuideViewCountView.as_view(), name='guide-view-count'),
    path('guides/<slug:slug>/comments/', GuideCommentListCreateView.as_view(), name='guide-comments'),
    path('guides/<slug:slug>/comments/<uuid:comment_id>/', GuideCommentDetailView.as_view(), name='guide-comment-detail'),
    path('guides/<slug:slug>/', TravelGuideDetailView.as_view(), name='guide-detail'),
    path('responsible-travel/', ResponsibleTravelListCreateView.as_view(), name='initiative-list'),
    path('responsible-travel/<slug:slug>/', ResponsibleTravelDetailView.as_view(), name='initiative-detail'),
]
