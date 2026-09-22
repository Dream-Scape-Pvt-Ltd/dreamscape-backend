"""
Convert TripDeparture seat tracking from a single mutable `available_seats`
column to a ledger: `booked_seats` (written by the booking flow) plus
`reserved_seats` (admin held-back block), with `available_seats` derived.

Ordering matters. The old `valid_departure_seats` constraint references
`available_seats`, so it is dropped before the column is; the backfill runs
while both the old column and the new counters exist; the new constraints go on
last, once every row already satisfies them.
"""
from django.db import migrations, models
from django.db.models import F, Q


def backfill_booked_seats(apps, schema_editor):
    """Seats previously implied by `max_seats - available_seats` become explicit."""
    TripDeparture = apps.get_model("trips", "TripDeparture")
    TripDeparture.objects.update(
        booked_seats=models.Case(
            models.When(available_seats__gt=F("max_seats"), then=models.Value(0)),
            default=F("max_seats") - F("available_seats"),
            output_field=models.PositiveIntegerField(),
        )
    )


def restore_available_seats(apps, schema_editor):
    """Reverse: rebuild the old column from the ledger."""
    TripDeparture = apps.get_model("trips", "TripDeparture")
    TripDeparture.objects.update(
        available_seats=F("max_seats") - F("reserved_seats") - F("booked_seats")
    )


class Migration(migrations.Migration):

    dependencies = [
        ("trips", "0003_trip_gallery_images_trip_hero_image_url"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="tripdeparture",
            name="valid_departure_seats",
        ),
        migrations.AddField(
            model_name="tripdeparture",
            name="booked_seats",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Seats consumed by bookings. The only counter the booking flow mutates.",
            ),
        ),
        migrations.AddField(
            model_name="tripdeparture",
            name="reserved_seats",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Seats held back by an admin (staff, guides, agent allotment). Not bookable.",
            ),
        ),
        migrations.AddField(
            model_name="tripdeparture",
            name="few_seats_threshold",
            field=models.PositiveIntegerField(
                default=3,
                help_text="At or below this many available seats the departure reads as 'Few Seats Left'.",
            ),
        ),
        migrations.AddField(
            model_name="tripdeparture",
            name="waitlist_enabled",
            field=models.BooleanField(
                default=True,
                help_text="Whether a full departure accepts waitlist entries.",
            ),
        ),
        migrations.AddField(
            model_name="tripdeparture",
            name="status_locked",
            field=models.BooleanField(
                default=False,
                help_text="Pin the admin-chosen status; automatic recomputation leaves it alone.",
            ),
        ),
        migrations.RunPython(backfill_booked_seats, restore_available_seats),
        migrations.RemoveField(
            model_name="tripdeparture",
            name="available_seats",
        ),
        migrations.AlterField(
            model_name="tripdeparture",
            name="status",
            field=models.CharField(
                choices=[
                    ("GUARANTEED", "Guaranteed Departure"),
                    ("LIMITED", "Limited Availability"),
                    ("SOLD_OUT", "Sold Out"),
                    ("WAITLIST", "Waitlist Only"),
                    ("CANCELLED", "Cancelled"),
                ],
                db_index=True,
                default="LIMITED",
                max_length=20,
            ),
        ),
        migrations.AddConstraint(
            model_name="tripdeparture",
            constraint=models.CheckConstraint(
                condition=Q(booked_seats__lte=F("max_seats") - F("reserved_seats")),
                name="valid_departure_seats",
            ),
        ),
        migrations.AddConstraint(
            model_name="tripdeparture",
            constraint=models.CheckConstraint(
                condition=Q(reserved_seats__lte=F("max_seats")),
                name="valid_departure_reserved_seats",
            ),
        ),
    ]
