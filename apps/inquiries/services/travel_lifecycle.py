"""
Moves a lead through the booked -> traveling -> completed part of the pipeline.

A lead in BOOKED, TRAVELING or COMPLETED occupies seats on its departure, so
every status change goes through ``transition_status``: it takes seats from the
departure ledger on the way in, gives them back on the way out, and records the
trip's revenue once it completes. Callers must not write ``Inquiry.status``
directly for these statuses, or the seat ledger drifts.
"""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from apps.inquiries.models import (
    Activity,
    ActivityChannel,
    Inquiry,
    InquiryStatus,
    SEAT_HOLDING_STATUSES,
)
from apps.trips.models import DepartureStatus, TripDeparture


def _hold_seats(inquiry, departure, travelers):
    """
    Put the lead's travellers on ``departure``. Seats already taken by the
    lead's own Booking on the same departure are not taken a second time.
    """
    if travelers < 1:
        raise serializers.ValidationError({"travelers_count": "At least one traveller is required."})

    locked = TripDeparture.objects.select_for_update().get(id=departure.id)
    if locked.status == DepartureStatus.CANCELLED:
        raise serializers.ValidationError({"departure_id": "This departure has been cancelled."})
    if inquiry.trip_id and locked.trip_id != inquiry.trip_id:
        raise serializers.ValidationError({"departure_id": "This departure belongs to a different trek."})

    booking = inquiry.converted_booking
    if booking and booking.departure_id == locked.id:
        # The booking flow already consumed these seats.
        inquiry.seats_held = 0
        inquiry.travelers_count = booking.num_travelers
    else:
        if locked.available_seats < travelers:
            raise serializers.ValidationError({
                "travelers_count": (
                    f"Only {locked.available_seats} seat(s) left on this departure; "
                    f"cannot book {travelers}."
                )
            })
        locked.booked_seats += travelers
        locked.recompute_status()
        locked.save(update_fields=["booked_seats", "status", "updated_at"])
        inquiry.seats_held = travelers
        inquiry.travelers_count = travelers

    inquiry.departure = locked
    if not inquiry.trip_id:
        inquiry.trip_id = locked.trip_id


def _release_seats(inquiry):
    """Give the lead's seats back to its departure and offer them to the waitlist."""
    from apps.bookings.services import promote_waitlist

    if inquiry.seats_held and inquiry.departure_id:
        locked = TripDeparture.objects.select_for_update().get(id=inquiry.departure_id)
        # max() guards against the counter going negative if an admin edited it.
        locked.booked_seats = max(locked.booked_seats - inquiry.seats_held, 0)
        locked.recompute_status()
        locked.save(update_fields=["booked_seats", "status", "updated_at"])
        promote_waitlist(locked)
    inquiry.seats_held = 0
    inquiry.travelers_count = None
    inquiry.revenue_usd = None


def _trip_revenue(inquiry):
    """The departure's per-person price times the people who travelled."""
    if not inquiry.departure_id or not inquiry.travelers_count:
        return None
    return (inquiry.departure.price_usd * Decimal(inquiry.travelers_count)).quantize(Decimal("0.01"))


def transition_status(inquiry, new_status, *, author=None, departure=None, travelers=None, reason=""):
    """
    Change a lead's status, keeping the departure's seat count and the trip
    revenue in step. Returns the saved inquiry.

    ``departure`` and ``travelers`` are used when the lead starts holding seats;
    they default to the lead's own departure and group size.
    """
    with transaction.atomic():
        inquiry = (
            Inquiry.objects.select_for_update(of=("self",))
            .select_related("departure", "converted_booking")
            .get(pk=inquiry.pk)
        )
        old_status = inquiry.status
        if new_status == old_status:
            return inquiry

        was_holding = old_status in SEAT_HOLDING_STATUSES
        will_hold = new_status in SEAT_HOLDING_STATUSES

        if will_hold and not was_holding:
            target = departure or inquiry.departure
            if target is None:
                raise serializers.ValidationError({
                    "departure_id": "Choose which departure this lead is booked on."
                })
            _hold_seats(inquiry, target, travelers or inquiry.group_size or 1)
        elif was_holding and not will_hold:
            _release_seats(inquiry)
        elif will_hold and departure is not None and departure.id != inquiry.departure_id:
            raise serializers.ValidationError({
                "departure_id": "Move the lead out of Booked before changing its departure."
            })

        if new_status == InquiryStatus.COMPLETED:
            inquiry.revenue_usd = _trip_revenue(inquiry)
            inquiry.completed_at = timezone.now()
        else:
            # Leaving COMPLETED takes the trip's revenue back out of its month.
            inquiry.completed_at = None
            if will_hold:
                inquiry.revenue_usd = None

        inquiry.status = new_status
        inquiry.save()

        body = f"Status changed from {old_status} to {new_status}."
        if reason:
            body = f"{body} {reason}"
        metadata = {"from_status": old_status, "to_status": new_status}
        if will_hold:
            metadata.update({"departure": str(inquiry.departure_id), "travelers": inquiry.travelers_count})
        if inquiry.revenue_usd is not None:
            metadata["revenue_usd"] = str(inquiry.revenue_usd)
        Activity.objects.create(
            inquiry=inquiry,
            author=author,
            channel=ActivityChannel.STATUS_CHANGE,
            body=body,
            metadata=metadata,
        )
    return inquiry


def advance_travel_statuses(today=None):
    """
    Move booked leads along by their departure dates: BOOKED -> TRAVELING once
    the departure starts, and BOOKED/TRAVELING -> COMPLETED once its end date
    has passed. Returns (started, completed) counts.
    """
    today = today or timezone.localdate()

    finished = Inquiry.objects.filter(
        status__in=[InquiryStatus.BOOKED, InquiryStatus.TRAVELING],
        departure__end_date__lt=today,
    )
    completed = 0
    for inquiry in finished:
        transition_status(inquiry, InquiryStatus.COMPLETED, reason="Trip end date passed.")
        completed += 1

    starting = Inquiry.objects.filter(
        status=InquiryStatus.BOOKED,
        departure__start_date__lte=today,
        departure__end_date__gte=today,
    )
    started = 0
    for inquiry in starting:
        transition_status(inquiry, InquiryStatus.TRAVELING, reason="Departure date reached.")
        started += 1

    return started, completed
