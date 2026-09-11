from django.conf import settings
from django.db import models
from apps.common.models.base import TimeStampedModel


class AgencyTier(models.TextChoices):
    BRONZE = "BRONZE", "Bronze (Standard Partner)"
    SILVER = "SILVER", "Silver (Preferred Agent)"
    GOLD = "GOLD", "Gold (Key Partner)"
    PLATINUM = "PLATINUM", "Platinum (Exclusive Global DMC)"


class B2BPartner(TimeStampedModel):
    """
    Travel agency, outbound tour operator, or corporate partner profile.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="b2b_profile",
    )
    company_name = models.CharField(max_length=255, db_index=True)
    country = models.CharField(max_length=100, db_index=True)
    registration_number = models.CharField(max_length=150, blank=True)
    website = models.URLField(max_length=255, blank=True)
    agency_tier = models.CharField(
        max_length=20,
        choices=AgencyTier.choices,
        default=AgencyTier.BRONZE,
        db_index=True,
    )
    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,  # e.g. 15.00 for 15%
    )
    approved = models.BooleanField(default=False, db_index=True)

    class Meta:
        db_table = "b2b_partners"
        ordering = ["company_name"]
        indexes = [
            models.Index(fields=["approved", "agency_tier"], name="b2b_appr_tier_idx"),
        ]

    def __str__(self):
        return f"{self.company_name} ({self.agency_tier}) - {self.country}"
