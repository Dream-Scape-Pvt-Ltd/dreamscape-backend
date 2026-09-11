from django.db import models
from apps.common.models.base import TimeStampedModel


class CommissionStatus(models.TextChoices):
    PENDING = "PENDING", "Pending Settlement"
    INVOICED = "INVOICED", "Invoice Generated"
    PAID = "PAID", "Commission Disbursed"
    DISPUTED = "DISPUTED", "Disputed / Adjusted"


class B2BBooking(TimeStampedModel):
    """
    Partner booking attribution, net settlement tracking, and commission ledger.
    """

    partner = models.ForeignKey(
        "b2b.B2BPartner",
        on_delete=models.PROTECT,
        related_name="partner_bookings",
    )
    booking = models.OneToOneField(
        "bookings.Booking",
        on_delete=models.PROTECT,
        related_name="b2b_attribution",
    )
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2)  # e.g. 15.00
    gross_amount_usd = models.DecimalField(max_digits=12, decimal_places=2)
    commission_amount_usd = models.DecimalField(max_digits=12, decimal_places=2)
    net_amount_usd = models.DecimalField(max_digits=12, decimal_places=2)
    commission_status = models.CharField(
        max_length=20,
        choices=CommissionStatus.choices,
        default=CommissionStatus.PENDING,
        db_index=True,
    )
    commission_invoiced_at = models.DateTimeField(null=True, blank=True)
    commission_paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "b2b_bookings"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["partner", "commission_status"], name="b2b_book_comm_idx"),
        ]

    def __str__(self):
        return f"{self.partner.company_name} - {self.booking.booking_reference} (Net: ${self.net_amount_usd})"
