from django.urls import path

from .views import (
    EmailDetailView,
    EmailListSendView,
    EmailResendView,
    TemplateDetailView,
    TemplateListCreateView,
    TemplateVariablesView,
)
from .webhook import ResendWebhookView

app_name = "emails"

urlpatterns = [
    path("", EmailListSendView.as_view(), name="email-list-send"),
    path("templates/", TemplateListCreateView.as_view(), name="template-list"),
    path("templates/variables/", TemplateVariablesView.as_view(), name="template-variables"),
    path("templates/<uuid:pk>/", TemplateDetailView.as_view(), name="template-detail"),
    path("webhook/resend/", ResendWebhookView.as_view(), name="resend-webhook"),
    path("<uuid:pk>/", EmailDetailView.as_view(), name="email-detail"),
    path("<uuid:pk>/resend/", EmailResendView.as_view(), name="email-resend"),
]
