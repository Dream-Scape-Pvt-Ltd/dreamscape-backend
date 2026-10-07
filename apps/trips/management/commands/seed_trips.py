"""
Seeds the trek & tour catalogue: trips, day-by-day itineraries, peak
expedition details and upcoming fixed departures.

    python manage.py seed_trips              # seed everything
    python manage.py seed_trips --dry-run    # print what would change
    python manage.py seed_trips --only everest-base-camp-trek

Idempotent: trips are matched by slug and updated in place, itinerary days are
rebuilt, and departures are matched by (trip, start_date). Existing departures
are never deleted, since bookings may point at them.

Destinations and categories come from the destinations seed migrations; this
command looks them up by slug and refuses to run if one is missing.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.destinations.models import ActivityCategory, Destination
from apps.trips.models import ItineraryDay, PeakExpeditionDetail, Trip, TripDeparture

from ._trip_seed_data import TRIPS


class Command(BaseCommand):
    help = "Create or update the seeded trek & tour catalogue."

    def add_arguments(self, parser):
        parser.add_argument("--only", help="Seed a single trip by slug.")
        parser.add_argument("--dry-run", action="store_true", help="Report what would change without writing.")

    def handle(self, *args, only=None, dry_run=False, **options):
        trips = [t for t in TRIPS if not only or t["slug"] == only]
        if not trips:
            raise CommandError(f"No seeded trip with slug {only!r}.")

        self._validate(trips)
        destinations = self._lookup(Destination, {t["destination"] for t in trips})
        categories = self._lookup(ActivityCategory, {t["category"] for t in trips})

        if dry_run:
            for t in trips:
                exists = Trip.objects.filter(slug=t["slug"]).exists()
                self.stdout.write(
                    f"{'update' if exists else 'create'} {t['slug']}: "
                    f"{len(t['itinerary'])} days, {len(t['departures'])} departures"
                )
            return

        with transaction.atomic():
            for t in trips:
                self._seed_trip(t, destinations[t["destination"]], categories[t["category"]])

        self.stdout.write(self.style.SUCCESS(f"Seeded {len(trips)} trips."))

    def _validate(self, trips):
        for t in trips:
            days = [d["day_number"] for d in t["itinerary"]]
            if days != list(range(1, t["duration_days"] + 1)):
                raise CommandError(f"{t['slug']}: itinerary days {days} don't match duration {t['duration_days']}.")

    def _lookup(self, model, slugs):
        found = {obj.slug: obj for obj in model.objects.filter(slug__in=slugs)}
        missing = slugs - found.keys()
        if missing:
            raise CommandError(f"Missing {model.__name__} slugs: {', '.join(sorted(missing))}. Run migrate first.")
        return found

    def _seed_trip(self, data, destination, category):
        fields = {
            k: v for k, v in data.items()
            if k not in ("slug", "destination", "category", "itinerary", "expedition", "departures")
        }
        trip, created = Trip.objects.update_or_create(
            slug=data["slug"],
            defaults={**fields, "destination": destination, "category": category},
        )

        trip.itinerary_days.all().delete()
        ItineraryDay.objects.bulk_create(ItineraryDay(trip=trip, **day) for day in data["itinerary"])

        if data.get("expedition"):
            PeakExpeditionDetail.objects.update_or_create(trip=trip, defaults=data["expedition"])

        new_departures = 0
        for start, guaranteed in data["departures"]:
            departure, dep_created = TripDeparture.objects.get_or_create(
                trip=trip,
                start_date=start,
                defaults={
                    "end_date": start + timedelta(days=trip.duration_days - 1),
                    "price_usd": trip.starting_price_usd,
                    "max_seats": trip.max_group_size,
                    "is_guaranteed": guaranteed,
                },
            )
            if dep_created:
                new_departures += 1
                if departure.recompute_status():
                    departure.save(update_fields=["status"])

        self.stdout.write(
            f"{'Created' if created else 'Updated'} {trip.slug}: "
            f"{len(data['itinerary'])} days, {new_departures} new departures"
        )
