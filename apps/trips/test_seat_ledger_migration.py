"""
Exercise the 0004 seat-ledger migration against real rows.

The ordinary test run migrates an empty database, so the RunPython backfill
never sees data. This walks the schema backwards to 0003, seeds departures the
old way, then migrates forward and checks the ledger came out right.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class SeatLedgerMigrationTests(TransactionTestCase):
    # These migrations create data the trip FK needs, so keep them applied.
    available_apps = None

    migrate_from = [("trips", "0003_trip_gallery_images_trip_hero_image_url")]
    migrate_to = [("trips", "0004_departure_seat_ledger")]

    def _migrate(self, targets):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(targets)
        executor.loader.build_graph()
        return executor.loader.project_state(targets).apps

    def test_backfill_converts_available_seats_into_booked_seats(self):
        old_apps = self._migrate(self.migrate_from)

        Destination = old_apps.get_model("destinations", "Destination")
        ActivityCategory = old_apps.get_model("destinations", "ActivityCategory")
        Trip = old_apps.get_model("trips", "Trip")
        TripDeparture = old_apps.get_model("trips", "TripDeparture")

        destination = Destination.objects.create(
            name="Annapurna", slug="annapurna-mig", country="NEPAL"
        )
        category = ActivityCategory.objects.create(name="Treks", slug="treks-mig")
        trip = Trip.objects.create(
            destination=destination,
            category=category,
            title="Annapurna Circuit",
            slug="annapurna-circuit-mig",
            duration_days=16,
            difficulty_grade="GRADE_3",
            starting_price_usd=Decimal("1500.00"),
            overview="Migration fixture",
        )
        start = date.today() + timedelta(days=30)

        cases = [
            # (max_seats, available_seats, expected booked_seats)
            (10, 10, 0),   # nothing sold
            (10, 4, 6),    # partly sold
            (10, 0, 10),   # sold out
        ]
        ids = []
        for index, (max_seats, available, _) in enumerate(cases):
            departure = TripDeparture.objects.create(
                trip=trip,
                start_date=start + timedelta(days=index),
                end_date=start + timedelta(days=index + 10),
                price_usd=Decimal("1500.00"),
                max_seats=max_seats,
                available_seats=available,
                status="LIMITED",
            )
            ids.append(departure.id)

        new_apps = self._migrate(self.migrate_to)
        Migrated = new_apps.get_model("trips", "TripDeparture")

        for departure_id, (max_seats, available, expected_booked) in zip(ids, cases):
            row = Migrated.objects.get(id=departure_id)
            self.assertEqual(row.booked_seats, expected_booked)
            self.assertEqual(row.reserved_seats, 0)
            # The ledger must reproduce the availability it replaced.
            self.assertEqual(row.max_seats - row.reserved_seats - row.booked_seats, available)

    def tearDown(self):
        # Leave the schema fully migrated so later tests in the run are not
        # handed a database rolled back to 0003.
        self._migrate(self.migrate_to)
        super().tearDown()
