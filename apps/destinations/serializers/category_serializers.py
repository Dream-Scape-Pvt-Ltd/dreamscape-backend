from rest_framework import serializers
from apps.destinations.models import ActivityCategory


class ActivityCategorySerializer(serializers.ModelSerializer):
    """
    Serializer for activity filter chips and category management.
    """

    class Meta:
        model = ActivityCategory
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "is_active",
        ]
