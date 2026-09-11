from django.db import models
from apps.common.models.base import TimeStampedModel


class PassengerDetail(TimeStampedModel):
    """
    Detailed traveler identity, passport verification, insurance, and medical declarations.
    Essential for national park permits, TIMS cards, and high-altitude rescue manifests.
    """

    booking = models.ForeignKey(
        "bookings.Booking",
        on_delete=models.CASCADE,
        related_name="passengers",
    )
    full_name = models.CharField(max_length=255)
    gender = models.CharField(max_length=20, blank=True)
    date_of_birth = models.DateField()
    passport_number = models.CharField(max_length=100, db_index=True)
    passport_expiry_date = models.DateField()
    nationality = models.CharField(max_length=100)
    insurance_provider = models.CharField(max_length=150)
    insurance_policy_number = models.CharField(max_length=100)
    insurance_emergency_phone = models.CharField(max_length=50)
    emergency_contact_name = models.CharField(max_length=255, blank=True)
    emergency_contact_phone = models.CharField(max_length=50, blank=True)
    dietary_requirements = models.TextField(blank=True)
    medical_conditions = models.TextField(blank=True)

    class Meta:
        db_table = "passenger_details"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.full_name} ({self.nationality}) - {self.booking.booking_reference}"
