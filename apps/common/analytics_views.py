import datetime
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from apps.common.permissions import IsSalesAgentOrAdmin
from apps.trips.models import Trip, TripDeparture
from apps.inquiries.models import Inquiry
from apps.bookings.models import Booking
from apps.content_cms.models import TravelGuide


def format_relative_time(dt):
    if not dt:
        return "recently"
    now = timezone.now()
    diff = now - dt
    seconds = int(diff.total_seconds())
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    if days == 1:
        return "Yesterday"
    if days < 7:
        return f"{days} days ago"
    return dt.strftime("%b %d, %Y")


class DashboardAnalyticsView(APIView):
    """
    GET /api/v1/analytics/dashboard/
    Provides aggregated, real-time analytics data for the admin dashboard:
    - Top 4 Metric Cards (Total Treks, New Inquiries, Active Expeditions, Monthly Revenue)
    - Month-over-Month (MoM) revenue growth
    - Historical 6-month revenue & bookings trend
    - Inquiries & Bookings status distributions
    - Dynamic Recent Activity feed synthesized across all models
    """

    permission_classes = [IsSalesAgentOrAdmin]

    def get(self, request, *args, **kwargs):
        current_time = timezone.now()
        start_of_current_month = current_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # 1. Total Treks Metrics
        total_treks = Trip.objects.count()
        active_treks = Trip.objects.filter(is_active=True).count()
        featured_treks = Trip.objects.filter(is_featured=True).count()
        treks_this_month = Trip.objects.filter(created_at__gte=start_of_current_month).count()

        # 2. Inquiries Metrics
        total_inquiries = Inquiry.objects.count()
        new_inquiries = Inquiry.objects.filter(status="NEW").count()
        inquiries_last_48h = Inquiry.objects.filter(
            created_at__gte=current_time - datetime.timedelta(hours=48)
        ).count()
        in_contact_inquiries = Inquiry.objects.filter(status="IN_CONTACT").count()
        traveling_inquiries = Inquiry.objects.filter(status="TRAVELING").count()

        # 3. Active Expeditions Metrics
        today = current_time.date()
        active_departures_count = TripDeparture.objects.filter(
            start_date__lte=today + datetime.timedelta(days=7),
            end_date__gte=today - datetime.timedelta(days=7),
            status__in=["GUARANTEED", "LIMITED", "SOLD_OUT"],
        ).count()

        active_bookings_count = Booking.objects.filter(
            status__in=["DEPOSIT_PAID", "FULLY_PAID"],
            trip_start_date__gte=today - datetime.timedelta(days=30),
            trip_start_date__lte=today + datetime.timedelta(days=30),
        ).count()

        active_expeditions = max(active_departures_count, traveling_inquiries, active_bookings_count)
        if active_expeditions == 0:
            future_departures = TripDeparture.objects.filter(start_date__gte=today).count()
            active_expeditions = max(traveling_inquiries, future_departures, 1 if total_treks > 0 and Booking.objects.filter(status__in=["DEPOSIT_PAID", "FULLY_PAID"]).exists() else 0)

        # 4 & 5. Revenue — earned when a trek completes (plus manual entries).
        # Shares one calculation with the Revenue page so the two always agree.
        from apps.inquiries.services.revenue import revenue_summary

        revenue = revenue_summary(6)
        current_month_revenue = revenue["totals"]["this_month"]
        last_month_revenue = revenue["totals"]["last_month"]
        total_revenue = revenue["totals"]["all_time"]
        mom_growth_percent = revenue["totals"]["mom_growth_percent"] or 0.0

        monthly_trends = []
        for row in revenue["monthly"]:
            year, month = (int(part) for part in row["month"].split("-"))
            m_start = datetime.datetime(year, month, 1, tzinfo=timezone.get_current_timezone())
            m_end = datetime.datetime(year + (month == 12), month % 12 + 1, 1, tzinfo=timezone.get_current_timezone())
            monthly_trends.append({
                "month_label": row["label"],
                "full_label": m_start.strftime("%b %Y"),
                "revenue": row["revenue"],
                "bookings_count": row["new_bookings"],
                "completed_trips": row["completed_trips"],
                "inquiries_count": Inquiry.objects.filter(created_at__gte=m_start, created_at__lt=m_end).count(),
            })

        # 6. Status Breakdown
        inquiries_by_status = {
            "NEW": Inquiry.objects.filter(status="NEW").count(),
            "ASSIGNED": Inquiry.objects.filter(status="ASSIGNED").count(),
            "IN_CONTACT": Inquiry.objects.filter(status="IN_CONTACT").count(),
            "BOOKED": Inquiry.objects.filter(status="BOOKED").count(),
            "TRAVELING": Inquiry.objects.filter(status="TRAVELING").count(),
            "COMPLETED": Inquiry.objects.filter(status="COMPLETED").count(),
            "CLOSED": Inquiry.objects.filter(status="CLOSED").count(),
        }

        bookings_by_status = {
            "PENDING": Booking.objects.filter(status="PENDING").count(),
            "DEPOSIT_PAID": Booking.objects.filter(status="DEPOSIT_PAID").count(),
            "FULLY_PAID": Booking.objects.filter(status="FULLY_PAID").count(),
            "CANCELLED": Booking.objects.filter(status="CANCELLED").count(),
            "REFUNDED": Booking.objects.filter(status="REFUNDED").count(),
        }

        # 7. Synthesized Dynamic Recent Activity Feed
        activities = []

        for inq in Inquiry.objects.select_related("trip").order_by("-created_at")[:5]:
            trip_name = inq.trip.title if inq.trip else "Himalayan Expedition"
            activities.append({
                "id": f"inq_{inq.id}",
                "type": "INQUIRY",
                "title": f"New inquiry from {inq.full_name}",
                "description": f"Interest in {trip_name} ({inq.group_size or 1} traveler{'s' if (inq.group_size or 1) > 1 else ''})",
                "timestamp": inq.created_at.isoformat(),
                "relative_time": format_relative_time(inq.created_at),
                "status": inq.status,
            })

        for bk in Booking.objects.select_related("departure__trip", "custom_trip").order_by("-created_at")[:5]:
            trip_title = (
                bk.departure.trip.title
                if bk.departure and bk.departure.trip
                else (bk.custom_trip.title if bk.custom_trip else "Adventure Trek")
            )
            activities.append({
                "id": f"bk_{bk.id}",
                "type": "BOOKING",
                "title": f"Booking {bk.booking_reference} ({bk.status.replace('_', ' ')})",
                "description": f"{bk.customer_name} booked {trip_title} (${float(bk.total_amount_usd):,.0f})",
                "timestamp": bk.created_at.isoformat(),
                "relative_time": format_relative_time(bk.created_at),
                "status": bk.status,
            })

        for tr in Trip.objects.order_by("-updated_at")[:3]:
            activities.append({
                "id": f"tr_{tr.id}",
                "type": "TREK",
                "title": f"Trek updated: {tr.title}",
                "description": f"{tr.duration_days} Days · Grade {tr.difficulty_grade.replace('GRADE_', '')} · Starting ${float(tr.starting_price_usd):,.0f}",
                "timestamp": tr.updated_at.isoformat(),
                "relative_time": format_relative_time(tr.updated_at),
                "status": "ACTIVE" if tr.is_active else "INACTIVE",
            })

        for gd in TravelGuide.objects.filter(is_published=True).order_by("-published_at")[:3]:
            pub_time = gd.published_at or gd.updated_at
            activities.append({
                "id": f"gd_{gd.id}",
                "type": "GUIDE",
                "title": f"Journal Guide: {gd.title}",
                "description": f"Published under {gd.get_category_display() if hasattr(gd, 'get_category_display') else gd.category}",
                "timestamp": pub_time.isoformat() if pub_time else current_time.isoformat(),
                "relative_time": format_relative_time(pub_time),
                "status": "PUBLISHED",
            })

        # Sort activities by timestamp descending
        activities.sort(key=lambda x: x["timestamp"], reverse=True)
        top_activities = activities[:8]

        data = {
            "metrics": {
                "total_treks": total_treks,
                "active_treks": active_treks,
                "featured_treks": featured_treks,
                "treks_this_month": treks_this_month,
                "new_inquiries": new_inquiries,
                "inquiries_last_48h": inquiries_last_48h,
                "total_inquiries": total_inquiries,
                "in_contact_inquiries": in_contact_inquiries,
                "active_expeditions": active_expeditions,
                "monthly_revenue": current_month_revenue,
                "last_month_revenue": last_month_revenue,
                "total_revenue": total_revenue,
                "mom_growth_percent": mom_growth_percent,
                "action_needed": new_inquiries > 0,
            },
            "monthly_trends": monthly_trends,
            "inquiries_by_status": inquiries_by_status,
            "bookings_by_status": bookings_by_status,
            "recent_activities": top_activities,
            "server_time": current_time.isoformat(),
        }

        return Response(data, status=status.HTTP_200_OK)
