from django.db import models
from apps.common.models.base import TimeStampedModel


class PaymentActionToken(TimeStampedModel):
    """
    Cryptographically secure single-use or time-bounded action token
    used for split balance payment links (e.g. 80% remaining balance payment before trek).
    """

    booking = models.ForeignKey(
        "bookings.Booking",
        on_delete=models.CASCADE,
        related_name="action_tokens",
    )
    token_hash = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
    )
    purpose = models.CharField(max_length=50)  # e.g. BALANCE_PAYMENT_80
    expires_at = models.DateTimeField(db_index=True)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "payment_action_tokens"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Token ({self.purpose}) for {self.booking.booking_reference}"
