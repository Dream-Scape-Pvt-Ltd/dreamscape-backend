from apps.common.models.base import TimeStampedModel


class Booking(TimeStampedModel):
    """
    Stub Booking model to satisfy foreign key dependencies during initial setup.
    Full schema will be implemented per databaseplan.md.
    """

    class Meta:
        db_table = "bookings"

    def __str__(self):
        return f"Booking {self.id}"
