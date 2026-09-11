from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.models.signals import pre_save
from django.dispatch import receiver

from apps.common.models.base import TimeStampedModel


class TripReview(TimeStampedModel):
    """
    Customer review and rating for a completed trip.
    Supports verified traveler badge via 1-to-1 linkage to confirmed bookings.
    """

    trip = models.ForeignKey(
        "trips.Trip",
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviews",
    )
    booking = models.OneToOneField(
        "bookings.Booking",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="review",
    )
    reviewer_name = models.CharField(max_length=255)
    reviewer_country = models.CharField(max_length=100, blank=True)
    rating_overall = models.PositiveSmallIntegerField()
    rating_guide = models.PositiveSmallIntegerField(null=True, blank=True)
    rating_itinerary = models.PositiveSmallIntegerField(null=True, blank=True)
    rating_safety = models.PositiveSmallIntegerField(null=True, blank=True)
    title = models.CharField(max_length=255, blank=True)
    content = models.TextField()
    travel_date = models.DateField(null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    is_published = models.BooleanField(default=False, db_index=True)

    class Meta:
        db_table = "trip_reviews"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(rating_overall__range=(1, 5)),
                name="valid_review_overall_rating",
            )
        ]
        indexes = [
            models.Index(fields=["trip", "is_published"], name="review_trip_published_idx"),
        ]

    def __str__(self):
        return f"{self.reviewer_name} - {self.trip.title} ({self.rating_overall}★)"


@receiver(pre_save, sender=TripReview)
def revoke_verified_badge_on_booking_loss(sender, instance, **kwargs):
    """
    Atomic integrity rule: if booking reference is disassociated,
    the verified traveler badge is revoked.
    """
    if instance.pk:
        original = TripReview.objects.filter(pk=instance.pk).first()
        if original and original.booking_id and not instance.booking_id:
            instance.is_verified = False
