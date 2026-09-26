from django.db import models
from apps.common.models.base import TimeStampedModel


class DifficultyGrade(models.TextChoices):
    EASY = "EASY", "Easy"
    NORMAL = "NORMAL", "Normal"
    DIFFICULT = "DIFFICULT", "Difficult"
    EXTREME = "EXTREME", "Extreme"


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
    hero_image_url = models.CharField(max_length=500, blank=True, default="")
    gallery_images = models.JSONField(default=list, blank=True)
    is_featured = models.BooleanField(default=False, db_index=True)
    is_highlighted = models.BooleanField(default=False, db_index=True)
    highlight_order = models.PositiveSmallIntegerField(null=True, blank=True, db_index=True)
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
