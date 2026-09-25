"""
Revenue is earned when a trek is completed, not when money arrives.

Two sources add up to it:
  * CRM leads in COMPLETED, each worth its recorded ``revenue_usd``
    (departure price x travellers) and dated by ``completed_at``;
  * manual ``RevenueEntry`` rows, dated by ``earned_on``.

Deposits, payments and bookings that have not travelled yet are deliberately
left out. ``revenue_summary`` is the one place that adds these up, so the
dashboard card and the Revenue page always agree.
"""
from datetime import date
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from apps.inquiries.models import Activity, ActivityChannel, Inquiry, InquiryStatus, RevenueEntry

UNASSIGNED = "Other / unassigned"
ZERO = Decimal("0.00")


def _month_starts(today, months):
    """The first day of each of the last ``months`` months, oldest first."""
    year, month = today.year, today.month
    starts = []
    for _ in range(months):
        starts.append(date(year, month, 1))
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return starts[::-1]


def _as_month(value):
    """TruncMonth gives an aware datetime for datetime fields and a date for date fields."""
    if value is None:
        return None
    if hasattr(value, "date"):
        value = timezone.localtime(value).date() if timezone.is_aware(value) else value.date()
    return value.replace(day=1)


def completed_leads():
    return Inquiry.objects.filter(
        status=InquiryStatus.COMPLETED,
        completed_at__isnull=False,
        revenue_usd__isnull=False,
    )


def _money(value):
    return float(value or ZERO)


def revenue_summary(months=6, today=None):
    today = today or timezone.localdate()
    starts = _month_starts(today, months)
    window_start = starts[0]
    this_month = starts[-1]
    last_month = _month_starts(today, 2)[0]
    tz = timezone.get_current_timezone()

    completed = completed_leads()
    manual = RevenueEntry.objects.all()

    # --- Monthly series ---------------------------------------------------
    completed_by_month = {
        _as_month(row["month"]): row
        for row in completed.filter(completed_at__date__gte=min(window_start, last_month))
        .annotate(month=TruncMonth("completed_at", tzinfo=tz))
        .values("month")
        .annotate(revenue=Sum("revenue_usd"), trips=Count("id"), travelers=Sum("travelers_count"))
    }
    manual_by_month = {
        _as_month(row["month"]): row["revenue"]
        for row in manual.filter(earned_on__gte=min(window_start, last_month))
        .annotate(month=TruncMonth("earned_on"))
        .values("month")
        .annotate(revenue=Sum("amount_usd"))
    }
    # New bookings: leads moved into BOOKED, plus website bookings that no lead
    # accounts for (a linked booking is already counted through its lead).
    booked_by_month = {
        _as_month(row["month"]): row["n"]
        for row in Activity.objects.filter(
            channel=ActivityChannel.STATUS_CHANGE,
            metadata__to_status=InquiryStatus.BOOKED,
            created_at__date__gte=window_start,
        )
        .annotate(month=TruncMonth("created_at", tzinfo=tz))
        .values("month")
        .annotate(n=Count("id"))
    }
    from apps.bookings.models import Booking

    web_bookings_by_month = {
        _as_month(row["month"]): row["n"]
        for row in Booking.objects.filter(created_at__date__gte=window_start, source_inquiry__isnull=True)
        .exclude(status__in=["CANCELLED", "REFUNDED"])
        .annotate(month=TruncMonth("created_at", tzinfo=tz))
        .values("month")
        .annotate(n=Count("id"))
    }

    def month_revenue(start):
        return (completed_by_month.get(start, {}).get("revenue") or ZERO) + (manual_by_month.get(start) or ZERO)

    monthly = []
    for start in starts:
        completed_row = completed_by_month.get(start, {})
        completed_rev = completed_row.get("revenue") or ZERO
        manual_rev = manual_by_month.get(start) or ZERO
        monthly.append({
            "month": start.strftime("%Y-%m"),
            "label": start.strftime("%b"),
            "full_label": start.strftime("%B %Y"),
            "completed_revenue": _money(completed_rev),
            "manual_revenue": _money(manual_rev),
            "revenue": _money(completed_rev + manual_rev),
            "completed_trips": completed_row.get("trips") or 0,
            "new_bookings": (booked_by_month.get(start) or 0) + (web_bookings_by_month.get(start) or 0),
        })

    # --- Totals -----------------------------------------------------------
    completed_totals = completed.aggregate(revenue=Sum("revenue_usd"), trips=Count("id"), travelers=Sum("travelers_count"))
    manual_total = manual.aggregate(total=Sum("amount_usd"))["total"] or ZERO
    completed_total = completed_totals["revenue"] or ZERO
    trips = completed_totals["trips"] or 0
    this_month_rev = month_revenue(this_month)
    last_month_rev = month_revenue(last_month)
    mom = None
    if last_month_rev > 0:
        mom = round(float((this_month_rev - last_month_rev) / last_month_rev * 100), 1)

    totals = {
        "all_time": _money(completed_total + manual_total),
        "completed_total": _money(completed_total),
        "manual_total": _money(manual_total),
        "this_month": _money(this_month_rev),
        "last_month": _money(last_month_rev),
        "mom_growth_percent": mom,
        "completed_trips": trips,
        "travelers_completed": completed_totals["travelers"] or 0,
        "avg_trip_value": _money(completed_total / trips) if trips else 0.0,
        "window_total": sum(row["revenue"] for row in monthly),
    }

    # --- Breakdowns -------------------------------------------------------
    destinations = {}
    for row in completed.values("trip__destination__name").annotate(revenue=Sum("revenue_usd")):
        name = row["trip__destination__name"] or UNASSIGNED
        destinations[name] = destinations.get(name, ZERO) + (row["revenue"] or ZERO)
    for row in manual.values("trip__destination__name").annotate(revenue=Sum("amount_usd")):
        name = row["trip__destination__name"] or UNASSIGNED
        destinations[name] = destinations.get(name, ZERO) + (row["revenue"] or ZERO)
    grand = sum(destinations.values(), ZERO)
    by_destination = [
        {"name": name, "revenue": _money(value), "share_percent": round(float(value / grand * 100), 1) if grand else 0.0}
        for name, value in sorted(destinations.items(), key=lambda item: item[1], reverse=True)
        if value > 0
    ]

    treks = {}
    for row in completed.filter(trip__isnull=False).values("trip__title", "trip__slug").annotate(
        revenue=Sum("revenue_usd"), trips=Count("id"), travelers=Sum("travelers_count")
    ):
        treks[row["trip__slug"]] = {
            "title": row["trip__title"], "slug": row["trip__slug"], "revenue": row["revenue"] or ZERO,
            "completed_trips": row["trips"], "travelers": row["travelers"] or 0,
        }
    for row in manual.filter(trip__isnull=False).values("trip__title", "trip__slug").annotate(revenue=Sum("amount_usd")):
        entry = treks.setdefault(row["trip__slug"], {
            "title": row["trip__title"], "slug": row["trip__slug"], "revenue": ZERO, "completed_trips": 0, "travelers": 0,
        })
        entry["revenue"] += row["revenue"] or ZERO
    by_trek = [
        {**row, "revenue": _money(row["revenue"])}
        for row in sorted(treks.values(), key=lambda item: item["revenue"], reverse=True)[:5]
    ]

    # --- Recent revenue events ------------------------------------------------
    recent = [
        {
            "source": "TREK_COMPLETED",
            "date": timezone.localtime(lead.completed_at).date().isoformat(),
            "label": f"{lead.full_name} completed {lead.trip.title if lead.trip_id else 'a trek'}",
            "detail": f"{lead.travelers_count or 0} traveller{'s' if (lead.travelers_count or 0) != 1 else ''}",
            "amount": _money(lead.revenue_usd),
            "reference": lead.inquiry_number,
        }
        for lead in completed.select_related("trip").order_by("-completed_at")[:8]
    ] + [
        {
            "source": "MANUAL",
            "date": entry.earned_on.isoformat(),
            "label": entry.description,
            "detail": entry.trip.title if entry.trip_id else "Added manually",
            "amount": _money(entry.amount_usd),
            "reference": str(entry.id),
        }
        for entry in manual.select_related("trip")[:8]
    ]
    recent.sort(key=lambda event: event["date"], reverse=True)

    return {
        "months": months,
        "totals": totals,
        "monthly": monthly,
        "by_destination": by_destination,
        "by_trek": by_trek,
        "recent": recent[:8],
    }
