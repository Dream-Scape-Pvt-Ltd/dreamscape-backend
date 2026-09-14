"""
apps.b2b URL configuration -- Phase 0 stub.
Endpoints will be registered in their respective implementation phase.
"""
from django.urls import path
from apps.b2b.views import (
    B2BRegisterView, B2BPartnerListView, B2BPartnerMeView, B2BPartnerApproveView,
    B2BAssetListView, B2BAssetDownloadView, B2BAssetFileView, B2BBookingListView, B2BCommissionUpdateView,
)

app_name = 'b2b'

urlpatterns = [
    path('register/', B2BRegisterView.as_view(), name='b2b-register'),
    path('partners/', B2BPartnerListView.as_view(), name='partner-list'),
    path('partners/me/', B2BPartnerMeView.as_view(), name='partner-me'),
    path('partners/<uuid:partner_id>/approve/', B2BPartnerApproveView.as_view(), name='partner-approve'),
    path('assets/', B2BAssetListView.as_view(), name='asset-list'),
    path('assets/<uuid:asset_id>/download/', B2BAssetDownloadView.as_view(), name='asset-download'),
    path('assets/<uuid:asset_id>/file/', B2BAssetFileView.as_view(), name='asset-file'),
    path('bookings/', B2BBookingListView.as_view(), name='b2b-booking-list'),
    path('bookings/<uuid:b2b_booking_id>/commission/', B2BCommissionUpdateView.as_view(), name='commission-update'),
]
