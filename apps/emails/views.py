from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils.html import escape, linebreaks
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.exceptions import _build_error_envelope
from apps.common.permissions import IsAdminRole, IsSalesAgentOrAdmin
from apps.common.throttling import WriteThrottleMixin
from apps.inquiries.models import Inquiry

from .models import EmailKind, EmailStatus, EmailTemplate, OutboundEmail
from .rendering import VARIABLES, inquiry_context, render
from .serializers import EmailTemplateSerializer, OutboundEmailSerializer, SendEmailSerializer
from .tasks import deliver_outbound_email, is_suppressed, queue_email


def _bad_request(message):
    return Response(_build_error_envelope("BAD_REQUEST", message, None), status=status.HTTP_400_BAD_REQUEST)


class TemplateListCreateView(generics.ListCreateAPIView):
    """Staff can read templates (to compose); only admins can create them."""

    serializer_class = EmailTemplateSerializer
    queryset = EmailTemplate.objects.all()
    pagination_class = None

    def get_permissions(self):
        return [IsAdminRole()] if self.request.method == "POST" else [IsSalesAgentOrAdmin()]


class TemplateDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = EmailTemplateSerializer
    queryset = EmailTemplate.objects.all()

    def get_permissions(self):
        return [IsSalesAgentOrAdmin()] if self.request.method == "GET" else [IsAdminRole()]

    def destroy(self, request, *args, **kwargs):
        if self.get_object().is_system:
            return _bad_request("System templates cannot be deleted.")
        return super().destroy(request, *args, **kwargs)


class TemplateVariablesView(APIView):
    permission_classes = [IsSalesAgentOrAdmin]

    def get(self, request):
        return Response([{"name": name, "label": label} for name, label in VARIABLES.items()])


class EmailListSendView(WriteThrottleMixin, generics.ListCreateAPIView):
    """GET: the sent log. POST: send an email (queued, then delivered by the outbox task)."""

    permission_classes = [IsSalesAgentOrAdmin]

    def get_serializer_class(self):
        return SendEmailSerializer if self.request.method == "POST" else OutboundEmailSerializer

    def get_queryset(self):
        qs = OutboundEmail.objects.select_related("inquiry", "template", "sent_by")
        params = self.request.query_params
        if params.get("status") in EmailStatus.values:
            qs = qs.filter(status=params["status"])
        if params.get("kind") in EmailKind.values:
            qs = qs.filter(kind=params["kind"])
        if params.get("inquiry"):
            qs = qs.filter(inquiry__inquiry_number=params["inquiry"])
        if params.get("search"):
            qs = qs.filter(Q(recipient__icontains=params["search"]) | Q(subject__icontains=params["search"]))
        return qs

    def create(self, request, *args, **kwargs):
        serializer = SendEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        template = data.get("template")
        inquiry = None
        if data.get("inquiry_number"):
            inquiry = get_object_or_404(Inquiry, inquiry_number=data["inquiry_number"])
        if is_suppressed(data["recipient"]):
            return _bad_request("This address bounced or reported spam earlier, so sending to it is blocked.")

        context = inquiry_context(inquiry) if inquiry else {}
        subject = data.get("subject") or template.subject
        if data.get("body_text"):
            # Edited or hand-written message: derive simple HTML from the text.
            text = data["body_text"]
            html = render(linebreaks(escape(text)), context, html=True)
        else:
            text, html = template.body_text, render(template.body_html, context, html=True)
        email = queue_email(
            recipient=data["recipient"],
            subject=render(subject, context, html=False),
            body_html=html,
            body_text=render(text, context, html=False),
            kind=EmailKind.TEMPLATE if template else EmailKind.MANUAL,
            reply_to=settings.INQUIRY_NOTIFY_EMAIL or "",
            template=template,
            inquiry=inquiry,
            sent_by=request.user,
        )
        return Response(OutboundEmailSerializer(email).data, status=status.HTTP_201_CREATED)


class EmailDetailView(generics.RetrieveAPIView):
    permission_classes = [IsSalesAgentOrAdmin]
    serializer_class = OutboundEmailSerializer
    queryset = OutboundEmail.objects.select_related("inquiry", "template", "sent_by")


class EmailResendView(APIView):
    """Re-queue an email that permanently failed."""

    permission_classes = [IsSalesAgentOrAdmin]

    def post(self, request, pk):
        email = get_object_or_404(OutboundEmail, pk=pk)
        if email.status != EmailStatus.FAILED:
            return _bad_request("Only failed emails can be sent again.")
        email.status, email.attempts, email.next_attempt_at, email.last_error = EmailStatus.QUEUED, 0, None, ""
        email.save(update_fields=["status", "attempts", "next_attempt_at", "last_error", "updated_at"])
        transaction.on_commit(lambda: deliver_outbound_email.delay(str(email.pk)), robust=True)
        return Response(OutboundEmailSerializer(email).data)
