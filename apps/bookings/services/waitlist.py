"""
Waitlist queue operations for full departures.

Every function here assumes the caller already holds (or is establishing) a row
lock on the departure, and is running inside ``transaction.atomic()`` — seat
release and the promotion that follows it must commit or fail together.
"""
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.bookings.models import DepartureWaitlistEntry, WaitlistStatus

#: How long a promoted traveller has to claim their seat before the offer
#: lapses and the next entry is served.
DEFAULT_OFFER_TTL_HOURS = 48


def _offer_ttl_hours() -> int:
    return getattr(settings, "WAITLIST_OFFER_TTL_HOURS", DEFAULT_OFFER_TTL_HOURS)


def join_waitlist(
    departure,
    *,
    customer_name,
    customer_email,
    customer_phone="",
    num_travelers=1,
    customer_user=None,
    source_inquiry=None,
):
    """
    Append a traveller to a departure's waitlist, or return their existing
    live entry if they are already queued.

    Idempotent on (departure, email) while an entry is WAITING, matching the
    ``unique_active_waitlist_entry`` constraint — a double form submission
    returns the same position rather than raising.
    """
    email = customer_email.strip().lower()

    existing = DepartureWaitlistEntry.objects.filter(
        departure=departure,
        customer_email=email,
        status=WaitlistStatus.WAITING,
    ).first()
    if existing:
        return existing

    last_position = (
        DepartureWaitlistEntry.objects.filter(departure=departure).aggregate(
            last=Max("position")
        )["last"]
        or 0
    )

    return DepartureWaitlistEntry.objects.create(
        departure=departure,
        customer_user=customer_user,
        source_inquiry=source_inquiry,
        customer_name=customer_name,
        customer_email=email,
        customer_phone=customer_phone or "",
        num_travelers=num_travelers,
        position=last_position + 1,
    )


def promote_waitlist(departure, *, limit=None):
    """
    Offer freed seats to the head of the queue.

    Walks the queue in position order, offering to each entry that fits in the
    seats currently available. An entry too large for the remaining space is
    skipped rather than blocking everyone behind it. Returns the entries that
    were offered.

    Called after any event that frees seats (cancellation, an admin raising
    ``max_seats`` or lowering ``reserved_seats``).
    """
    if departure.status_locked and departure.status in ("SOLD_OUT", "CANCELLED"):
        # An admin has deliberately pinned this departure closed.
        return []

    seats_free = departure.available_seats
    if seats_free <= 0:
        return []

    # Seats already spoken for by live offers are not free to offer again.
    outstanding = DepartureWaitlistEntry.objects.filter(
        departure=departure,
        status=WaitlistStatus.OFFERED,
        offer_expires_at__gt=timezone.now(),
    )
    seats_free -= sum(entry.num_travelers for entry in outstanding)
    if seats_free <= 0:
        return []

    candidates = (
        DepartureWaitlistEntry.objects.select_for_update()
        .filter(departure=departure, status=WaitlistStatus.WAITING)
        .order_by("position")
    )

    now = timezone.now()
    expires_at = now + timedelta(hours=_offer_ttl_hours())
    promoted = []

    for entry in candidates:
        if limit is not None and len(promoted) >= limit:
            break
        if entry.num_travelers > seats_free:
            continue
        entry.status = WaitlistStatus.OFFERED
        entry.offered_at = now
        entry.offer_expires_at = expires_at
        entry.save(update_fields=["status", "offered_at", "offer_expires_at", "updated_at"])
        seats_free -= entry.num_travelers
        promoted.append(entry)
        if seats_free <= 0:
            break

    for entry in promoted:
        _queue_offer_notification(entry)

    return promoted


def _queue_offer_notification(entry):
    """
    Dispatch the "a seat opened up" email after the surrounding transaction
    commits, so the traveller is never told about a seat that got rolled back.

    Import is local: apps.bookings.tasks imports the models this module uses.
    """
    from apps.bookings.tasks import send_waitlist_offer_email

    transaction.on_commit(lambda: send_waitlist_offer_email.delay(str(entry.id)))


def expire_stale_offers():
    """
    Lapse offers nobody claimed and serve whoever is next.

    Returns the number of offers expired. Intended for a Celery Beat job.
    """
    from apps.trips.models import TripDeparture

    now = timezone.now()
    stale = DepartureWaitlistEntry.objects.filter(
        status=WaitlistStatus.OFFERED,
        offer_expires_at__lte=now,
    )
    departure_ids = list(stale.values_list("departure_id", flat=True).distinct())
    expired_count = stale.update(status=WaitlistStatus.EXPIRED, updated_at=now)

    for departure_id in departure_ids:
        with transaction.atomic():
            departure = TripDeparture.objects.select_for_update().get(id=departure_id)
            promote_waitlist(departure)

    return expired_count
