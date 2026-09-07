from apps.common.models.base import TimeStampedModel


class Inquiry(TimeStampedModel):
    """
    Stub Inquiry model to satisfy foreign key dependencies during initial setup.
    Full schema will be implemented per databaseplan.md.
    """

    class Meta:
        db_table = "inquiries"

    def __str__(self):
        return f"Inquiry {self.id}"
