"""
apps.search URL configuration -- Phase 0 stub.
Endpoints will be registered in their respective implementation phase.
"""
from django.urls import path
from apps.search.views import UnifiedSearchView

app_name = 'search'

urlpatterns = [
    path('', UnifiedSearchView.as_view(), name='unified-search'),
]
