from django.conf import settings
from django.db import models
from apps.common.models.base import TimeStampedModel


class InquiryType(models.TextChoices):
    GENERAL = "GENERAL", "General Inquiry"
    JOURNEY = "JOURNEY", "Specific Journey / Trip"
    TAILOR_MADE = "TAILOR_MADE", "Custom / Tailor-Made Itinerary"
    PARTNER_DMC = "PARTNER_DMC", "B2B / Partner DMC"
    EXISTING_TRAVELLER = "EXISTING_TRAVELLER", "Existing Traveler Support"


class InquiryStatus(models.TextChoices):
    NEW = "NEW", "New Lead"
    ASSIGNED = "ASSIGNED", "Assigned to Agent"
    IN_CONTACT = "IN_CONTACT", "In Active Communication"
    TRAVELING = "TRAVELING", "Currently Traveling"
    COMPLETED = "COMPLETED", "Completed Trip"
    CLOSED = "CLOSED", "Closed / Not Converted"


class Inquiry(TimeStampedModel):
    """
    Inbound CRM lead, trip inquiry, or tailor-made custom adventure request.
    """

    inquiry_number = models.CharField(
        max_length=30,
        unique=True,
        db_index=True,
    )
    inquiry_type = models.CharField(
        max_length=30,
        choices=InquiryType.choices,
        db_index=True,
    )
    trip = models.ForeignKey(
        "trips.Trip",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inquiries",
    )
    departure = models.ForeignKey(
        "trips.TripDeparture",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inquiries",
    )
    full_name = models.CharField(max_length=255)
    email = models.EmailField(db_index=True)
    phone = models.CharField(max_length=50, blank=True)
    whatsapp_number = models.CharField(max_length=50, blank=True)
    message = models.TextField(blank=True)
    preferred_dates = models.CharField(max_length=255, blank=True)
    estimated_budget = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    group_size = models.PositiveIntegerField(null=True, blank=True)
    lead_source = models.CharField(max_length=50, default="WEBSITE")
    status = models.CharField(
        max_length=20,
        choices=InquiryStatus.choices,
        default=InquiryStatus.NEW,
        db_index=True,
    )
    assigned_agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_inquiries",
    )

    class Meta:
        db_table = "inquiries"
        ordering = ["-created_at"]
        verbose_name_plural = "Inquiries"
        indexes = [
            models.Index(fields=["status", "created_at"], name="inq_status_created_idx"),
            models.Index(fields=["email", "status"], name="inq_email_status_idx"),
        ]

    def __str__(self):
        return f"{self.inquiry_number} - {self.full_name} ({self.inquiry_type})"
