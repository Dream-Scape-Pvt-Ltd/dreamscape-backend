from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.common.models.base import TimeStampedModel


class RevenueEntry(TimeStampedModel):
    """
    Revenue recorded by hand, for income that does not come from a completed
    CRM lead (e.g. an offline group, a private add-on). Counted in the month
    of ``earned_on`` alongside completed-trip revenue.
    """

    amount_usd = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    earned_on = models.DateField(default=timezone.localdate, db_index=True)
    description = models.CharField(max_length=255)
    trip = models.ForeignKey(
        "trips.Trip",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="revenue_entries",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="revenue_entries",
    )

    class Meta:
        db_table = "crm_revenue_entries"
        ordering = ["-earned_on", "-created_at"]
        verbose_name_plural = "Revenue entries"

    def __str__(self):
        return f"${self.amount_usd} on {self.earned_on}: {self.description}"
