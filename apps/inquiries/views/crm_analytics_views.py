from datetime import datetime

from decimal import Decimal

from django.db.models import Avg, Count, F, Q, Sum
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import IsSalesAgentOrAdmin
from apps.inquiries.models import Inquiry, InquiryStatus, InquiryType, LostReason
from apps.trips.models import Trip


class PipelineSummaryView(APIView):
    """
    GET /api/v1/crm/pipeline-summary/
        Lead counts grouped by status, by sales agent, and by inquiry type.
        Powers the Kanban pipeline view and dashboard tiles.
        Permissions: IsSalesAgentOrAdmin.
    """

    permission_classes = [IsSalesAgentOrAdmin]

    def get(self, request, *args, **kwargs):
        by_status = {
            choice_value: Inquiry.objects.filter(status=choice_value).count()
            for choice_value, _ in InquiryStatus.choices
        }

        by_type = {
            choice_value: Inquiry.objects.filter(inquiry_type=choice_value).count()
            for choice_value, _ in InquiryType.choices
        }

        open_statuses_excluded = [InquiryStatus.CLOSED, InquiryStatus.COMPLETED]

        by_agent = list(
            Inquiry.objects.filter(assigned_agent__isnull=False)
            .exclude(status__in=open_statuses_excluded)
            .values(
                "assigned_agent_id",
                "assigned_agent__first_name",
                "assigned_agent__last_name",
                "assigned_agent__email",
            )
            .annotate(open_leads=Count("id"))
            .order_by("-open_leads")
        )

        unassigned = (
            Inquiry.objects.filter(assigned_agent__isnull=True)
            .exclude(status__in=open_statuses_excluded)
            .count()
        )

        sla_breached = Inquiry.objects.filter(sla_breached=True, status=InquiryStatus.NEW).count()

        return Response(
            {
                "by_status": by_status,
                "by_type": by_type,
                "by_agent": by_agent,
                "unassigned_open_leads": unassigned,
                "sla_breached_count": sla_breached,
                "server_time": timezone.now().isoformat(),
            },
            status=status.HTTP_200_OK,
        )


class FunnelView(APIView):
    """
    GET /api/v1/crm/funnel/?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD
        Conversion funnel: lead volume by stage, overall conversion rate
        (converted_booking set / total in range), lost-reason breakdown,
        and average days-to-close for resolved leads.
        Permissions: IsSalesAgentOrAdmin.
    """

    permission_classes = [IsSalesAgentOrAdmin]

    def get(self, request, *args, **kwargs):
        qs = Inquiry.objects.all()

        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        if date_from:
            qs = qs.filter(created_at__date__gte=datetime.strptime(date_from, "%Y-%m-%d").date())
        if date_to:
            qs = qs.filter(created_at__date__lte=datetime.strptime(date_to, "%Y-%m-%d").date())

        total = qs.count()
        converted = qs.filter(converted_booking__isnull=False).count()
        closed_lost = qs.filter(status=InquiryStatus.CLOSED, converted_booking__isnull=True).count()

        conversion_rate = round((converted / total) * 100, 1) if total else 0.0

        funnel_stages = [
            {"status": choice_value, "label": label, "count": qs.filter(status=choice_value).count()}
            for choice_value, label in InquiryStatus.choices
        ]

        lost_reasons = {
            choice_value: qs.filter(status=InquiryStatus.CLOSED, lost_reason=choice_value).count()
            for choice_value, _ in LostReason.choices
        }

        resolved = qs.filter(converted_at__isnull=False)
        avg_days_to_close = None
        if resolved.exists():
            avg_seconds = resolved.annotate(
                resolution_seconds=F("converted_at") - F("created_at")
            ).aggregate(avg=Avg("resolution_seconds"))["avg"]
            if avg_seconds:
                avg_days_to_close = round(avg_seconds.total_seconds() / 86400, 1)

        return Response(
            {
                "total_leads": total,
                "converted": converted,
                "closed_lost": closed_lost,
                "conversion_rate_percent": conversion_rate,
                "funnel_stages": funnel_stages,
                "lost_reasons": lost_reasons,
                "avg_days_to_close": avg_days_to_close,
                "date_from": date_from,
                "date_to": date_to,
            },
            status=status.HTTP_200_OK,
        )


class TrekPipelineView(APIView):
    """
    GET /api/v1/inquiries/crm/treks/
        The CRM organised by active trek: for each active trek, its lead count
        in every pipeline status, the people who have completed it, and the
        revenue those completed trips earned (departure price x travellers).
        Permissions: IsSalesAgentOrAdmin.
    """

    permission_classes = [IsSalesAgentOrAdmin]

    def get(self, request, *args, **kwargs):
        status_counts = {
            f"count_{value}": Count("inquiries", filter=Q(inquiries__status=value))
            for value, _ in InquiryStatus.choices
        }
        completed = Q(inquiries__status=InquiryStatus.COMPLETED)
        treks = (
            Trip.objects.filter(is_active=True)
            .select_related("destination")
            .annotate(
                **status_counts,
                travelers_completed=Sum("inquiries__travelers_count", filter=completed),
                revenue_usd=Sum("inquiries__revenue_usd", filter=completed),
            )
            .order_by("title")
        )

        results = []
        for trek in treks:
            by_status = {value: getattr(trek, f"count_{value}") for value, _ in InquiryStatus.choices}
            results.append({
                "id": str(trek.id),
                "slug": trek.slug,
                "title": trek.title,
                "destination_name": trek.destination.name if trek.destination_id else None,
                "by_status": by_status,
                "total_leads": sum(by_status.values()),
                "travelers_completed": trek.travelers_completed or 0,
                "revenue_usd": str(trek.revenue_usd or Decimal("0.00")),
            })

        return Response(
            {
                "results": results,
                "total_revenue_usd": str(sum((Decimal(row["revenue_usd"]) for row in results), Decimal("0.00"))),
            },
            status=status.HTTP_200_OK,
        )
