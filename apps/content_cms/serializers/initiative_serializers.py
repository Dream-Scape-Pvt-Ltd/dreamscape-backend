from rest_framework import serializers
from apps.content_cms.models import ResponsibleTravelInitiative


class ResponsibleTravelSerializer(serializers.ModelSerializer):
    """
    Serializer for porter welfare and ecological pledges.
    """

    class Meta:
        model = ResponsibleTravelInitiative
        fields = [
            "id",
            "title",
            "slug",
            "pillars",
            "content",
            "is_published",
        ]
        read_only_fields = ['id']
