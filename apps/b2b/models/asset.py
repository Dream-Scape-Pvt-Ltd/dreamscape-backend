from django.db import models
from apps.common.models.base import TimeStampedModel
from apps.b2b.models.partner import AgencyTier
from apps.b2b.storage import PrivateAssetStorage


class AssetType(models.TextChoices):
    WHITE_LABEL_ITINERARY = "WHITE_LABEL_ITINERARY", "White-Label Itinerary (PDF/Doc)"
    ROUTE_MAP = "ROUTE_MAP", "High-Resolution Route Map"
    MARKETING_MEDIA = "MARKETING_MEDIA", "Marketing Photos & B-Roll"


class B2BAsset(TimeStampedModel):
    """
    Tier-gated marketing collateral, unbranded itineraries, and sales kits for B2B agencies.
    """

    trip = models.ForeignKey(
        "trips.Trip",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="b2b_assets",
    )
    title = models.CharField(max_length=255)
    asset_type = models.CharField(
        max_length=30,
        choices=AssetType.choices,
        db_index=True,
    )
    file = models.FileField(upload_to="b2b_assets/", storage=PrivateAssetStorage())
    minimum_tier = models.CharField(
        max_length=20,
        choices=AgencyTier.choices,
        default=AgencyTier.BRONZE,
        db_index=True,
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "b2b_assets"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.asset_type}) - Min: {self.minimum_tier}"
