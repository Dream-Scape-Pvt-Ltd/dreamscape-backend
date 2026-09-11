from django.db import models
from apps.common.models.base import TimeStampedModel


class TailorMadeRequest(TimeStampedModel):
    """
    Detailed bespoke adventure preferences including GeoJSON custom routes and waypoints.
    """

    inquiry = models.OneToOneField(
        "inquiries.Inquiry",
        on_delete=models.CASCADE,
        related_name="tailor_made_detail",
    )
    custom_destinations = models.JSONField(default=list, blank=True)
    desired_activities = models.JSONField(default=list, blank=True)
    fitness_level = models.CharField(max_length=100, blank=True)
    accommodation_standard = models.CharField(max_length=100, blank=True)
    guide_language_preference = models.CharField(max_length=50, blank=True)
    custom_route_coordinates = models.JSONField(default=list, blank=True)
    waypoints = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "tailor_made_requests"

    def __str__(self):
        return f"Tailor Made Specs for {self.inquiry.inquiry_number}"
