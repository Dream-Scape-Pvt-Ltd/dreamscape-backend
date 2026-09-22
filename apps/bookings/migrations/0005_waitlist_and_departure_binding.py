"""
Add the departure waitlist queue, and require every booking to be anchored to
either a published departure or a tailor-made trip.

The binding is a check constraint rather than a non-null FK so that tailor-made
bookings (which carry `custom_trip` and no departure) stay legal and no data
backfill is needed.
"""
import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0004_booking_access_token"),
        ("trips", "0004_departure_seat_ledger"),
        ("inquiries", "0003_backfill_customers"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="DepartureWaitlistEntry",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("customer_name", models.CharField(max_length=255)),
                ("customer_email", models.EmailField(db_index=True, max_length=254)),
                ("customer_phone", models.CharField(blank=True, default="", max_length=50)),
                ("num_travelers", models.PositiveIntegerField(default=1)),
                (
                    "position",
                    models.PositiveIntegerField(
                        help_text="Queue position, 1-based. Lower is served first."
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("WAITING", "Waiting"),
                            ("OFFERED", "Seat Offered"),
                            ("CONVERTED", "Converted to Booking"),
                            ("EXPIRED", "Offer Expired"),
                            ("CANCELLED", "Cancelled"),
                        ],
                        db_index=True,
                        default="WAITING",
                        max_length=20,
                    ),
                ),
                ("offered_at", models.DateTimeField(blank=True, null=True)),
                ("offer_expires_at", models.DateTimeField(blank=True, null=True)),
                (
                    "departure",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="waitlist_entries",
                        to="trips.tripdeparture",
                    ),
                ),
                (
                    "customer_user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="waitlist_entries",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "source_inquiry",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="waitlist_entries",
                        to="inquiries.inquiry",
                    ),
                ),
                (
                    "converted_booking",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="source_waitlist_entry",
                        to="bookings.booking",
                    ),
                ),
            ],
            options={
                "db_table": "departure_waitlist_entries",
                "ordering": ["departure", "position"],
            },
        ),
        migrations.AddIndex(
            model_name="departurewaitlistentry",
            index=models.Index(
                fields=["departure", "position"], name="wait_dep_position_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="departurewaitlistentry",
            index=models.Index(
                fields=["status", "offer_expires_at"], name="wait_status_expiry_idx"
            ),
        ),
        migrations.AddConstraint(
            model_name="departurewaitlistentry",
            constraint=models.UniqueConstraint(
                condition=Q(status="WAITING"),
                fields=("departure", "customer_email"),
                name="unique_active_waitlist_entry",
            ),
        ),
        migrations.AddConstraint(
            model_name="departurewaitlistentry",
            constraint=models.CheckConstraint(
                condition=Q(num_travelers__gte=1),
                name="waitlist_minimum_one_traveler",
            ),
        ),
        migrations.AddConstraint(
            model_name="booking",
            constraint=models.CheckConstraint(
                condition=Q(departure__isnull=False) | Q(custom_trip__isnull=False),
                name="booking_requires_departure_or_custom_trip",
            ),
        ),
    ]
