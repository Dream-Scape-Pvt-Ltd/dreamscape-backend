from django.conf import settings
from django.db import models
from django.utils import timezone
from apps.common.models.base import TimeStampedModel


class GuideCategory(models.TextChoices):
    ADVENTURE = "ADVENTURE", "Adventure"
    TRAVEL_TIPS = "TRAVEL_TIPS", "Travel Tips"
    CULTURE = "CULTURE", "Culture"
    NATURE = "NATURE", "Nature"
    FOOD = "FOOD", "Food"
    OTHER = "OTHER", "Other"


class TravelGuide(TimeStampedModel):
    """
    Editorial guide and high-ranking SEO content resource for Himalayan travel.
    """

    destination = models.ForeignKey(
        "destinations.Destination",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="guides",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="authored_guides",
    )
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, db_index=True)
    country = models.CharField(max_length=100, db_index=True)
    region = models.CharField(max_length=150, blank=True)
    category = models.CharField(
        max_length=30,
        choices=GuideCategory.choices,
        db_index=True,
    )
    markdown_content = models.TextField()
    hero_image_url = models.URLField(max_length=500, blank=True)
    gallery_images = models.JSONField(default=list, blank=True)
    meta_title = models.CharField(max_length=255, blank=True)
    meta_description = models.CharField(max_length=500, blank=True)
    canonical_url = models.URLField(max_length=500, blank=True)
    is_published = models.BooleanField(default=False, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True)
    view_count = models.PositiveBigIntegerField(default=0)

    class Meta:
        db_table = "travel_guides"
        ordering = ["-published_at", "-created_at"]
        indexes = [
            models.Index(fields=["is_published", "category"], name="guide_pub_cat_idx"),
            models.Index(fields=["country", "category"], name="guide_country_cat_idx"),
        ]

    def save(self, *args, **kwargs):
        if self.is_published and not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} ({self.category})"


class BlogComment(TimeStampedModel):
    guide = models.ForeignKey(
        TravelGuide,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="blog_comments",
    )
    author_name = models.CharField(max_length=255)
    body = models.TextField()
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "blog_comments"
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(fields=["guide", "is_active", "created_at"], name="blog_comment_list_idx"),
        ]

    def __str__(self):
        return f"Comment by {self.author_name} on {self.guide.title}"
