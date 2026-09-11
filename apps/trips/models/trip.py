from django.db import models
from apps.common.models.base import TimeStampedModel


class DifficultyGrade(models.TextChoices):
    GRADE_1 = "GRADE_1", "Grade 1 - Easy"
    GRADE_2 = "GRADE_2", "Grade 2 - Moderate"
    GRADE_3 = "GRADE_3", "Grade 3 - Demanding"
    GRADE_4 = "GRADE_4", "Grade 4 - Strenuous"
    GRADE_5 = "GRADE_5", "Grade 5 - Challenging"
    ALPINE = "ALPINE", "Alpine / Technical"


class Trip(TimeStampedModel):
    """
    Core journey entity representing trekking routes, peak expeditions, and tours.
    """

    destination = models.ForeignKey(
        "destinations.Destination",
        on_delete=models.PROTECT,
        related_name="trips",
    )
    category = models.ForeignKey(
        "destinations.ActivityCategory",
        on_delete=models.PROTECT,
        related_name="trips",
    )
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, db_index=True)
    duration_days = models.PositiveIntegerField(db_index=True)
    altitude_max_meters = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    difficulty_grade = models.CharField(
        max_length=20,
        choices=DifficultyGrade.choices,
        db_index=True,
    )
    min_group_size = models.PositiveIntegerField(default=1)
    max_group_size = models.PositiveIntegerField(default=14)
    best_seasons = models.JSONField(default=list, blank=True)
    inclusions = models.JSONField(default=list, blank=True)
    exclusions = models.JSONField(default=list, blank=True)
    packing_list = models.JSONField(default=list, blank=True)
    starting_price_usd = models.DecimalField(max_digits=12, decimal_places=2, db_index=True)
    single_supplement_usd = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    overview = models.TextField()
    is_featured = models.BooleanField(default=False, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "trips"
        ordering = ["-is_featured", "title"]
        indexes = [
            models.Index(fields=["destination", "is_active"], name="trip_dest_active_idx"),
            models.Index(fields=["category", "is_active"], name="trip_cat_active_idx"),
            models.Index(fields=["difficulty_grade", "duration_days"], name="trip_diff_dur_idx"),
        ]

    def __str__(self):
        return f"{self.title} ({self.duration_days} Days)"
