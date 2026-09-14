"""
apps.faq URL configuration -- Phase 0 stub.
Endpoints will be registered in their respective implementation phase.
"""
from django.urls import path
from apps.faq.views import FAQListCreateView, FAQDetailView

app_name = 'faq'

urlpatterns = [
    path('', FAQListCreateView.as_view(), name='faq-list'),
    path('<uuid:pk>/', FAQDetailView.as_view(), name='faq-detail'),
]
